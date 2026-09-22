# Iteration 9 - Racontelle: re-attributed free memories must disappear from archive "Tous" view.
# Flow: create free capsule (no resident) + question capsule (Claire) via UI,
# verify Tous shows both, reassign free capsule to Claire via Modifier,
# verify it disappears from Tous, stays visible via Claire filter and Claire's fiche.
# Regressions: archive search, play/pause, auto-transcription.
import asyncio
import json

from playwright.async_api import async_playwright

BASE_URL = "https://ehpad-recall.preview.emergentagent.com"
CLAIRE = "96539515-8cea-41ab-b588-8e5911700a85"
results = {}


async def list_cards(page):
    return await page.evaluate("""() => {
      const edits = Array.from(document.querySelectorAll('[data-testid^="capsule-edit-"]'));
      return edits.map(el => {
        const id = el.getAttribute('data-testid').replace('capsule-edit-','');
        let node = el.parentElement;
        while (node && !node.querySelector('[data-testid^="capsule-play-"]')) node = node.parentElement;
        return { id, text: node ? (node.textContent||'').slice(0,200) : '' };
      });
    }""")


async def record_and_save(page):
    await page.wait_for_selector('[data-testid="workshop-record"]', timeout=15000)
    await page.click('[data-testid="workshop-record"]', force=True)
    await page.wait_for_timeout(3000)
    await page.click('[data-testid="workshop-stop"]', force=True)
    await page.wait_for_selector('[data-testid="workshop-save"]', timeout=8000)
    await page.click('[data-testid="workshop-save"]', force=True)
    await page.wait_for_timeout(2500)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path="/root/bin/chromium",
            headless=True,
            args=[
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                "--autoplay-policy=no-user-gesture-required",
                "--no-sandbox",
            ],
        )
        ctx = await browser.new_context(
            viewport={"width": 390, "height": 844},
            permissions=["microphone"],
        )
        page = await ctx.new_page()
        page.on("console", lambda msg: print(f"CONSOLE_ERR: {msg.text}") if msg.type == "error" else None)
        try:
            await page.goto(BASE_URL, timeout=60000)
            await page.wait_for_selector('[data-testid="home-screen"]', timeout=90000)
            await page.wait_for_timeout(3000)
            results["home_load"] = await page.is_visible(f'[data-testid="home-profile-{CLAIRE}"]')
            print(f"STEP1 home loaded, Claire visible={results['home_load']}")

            # STEP 2: free capsule without resident
            await page.click('[data-testid="home-free-mode"]', force=True)
            await record_and_save(page)
            results["free_save"] = await page.is_visible('[data-testid="workshop-listen-question"]')
            print(f"STEP2 free saved, question mode shown={results['free_save']}")
            await page.click('[data-testid="workshop-back"]', force=True)
            await page.wait_for_selector('[data-testid="home-screen"]', timeout=8000)

            # STEP 3: question capsule for Claire
            await page.click(f'[data-testid="home-profile-{CLAIRE}"]', force=True)
            await page.wait_for_selector('[data-testid="profile-start-workshop"]', timeout=8000)
            await page.click('[data-testid="profile-start-workshop"]', force=True)
            await page.wait_for_selector('[data-testid="workshop-mode-question"]', timeout=8000)
            await page.click('[data-testid="workshop-mode-question"]', force=True)
            await page.wait_for_timeout(500)
            await record_and_save(page)
            results["question_save"] = True
            print("STEP3 question capsule saved")
            await page.click('[data-testid="workshop-back"]', force=True)
            await page.wait_for_selector('[data-testid="profile-back"]', timeout=8000)
            await page.click('[data-testid="profile-back"]', force=True)
            await page.wait_for_selector('[data-testid="home-screen"]', timeout=8000)

            # STEP 4: archive Tous - both capsules visible
            await page.click('[data-testid="home-archive"]', force=True)
            await page.wait_for_selector('[data-testid="archive-search"]', timeout=8000)
            await page.wait_for_timeout(6500)  # let save notices auto-dismiss
            cards = await list_cards(page)
            free_cards = [c for c in cards if "Souvenir libre" in c["text"]]
            question_cards = [c for c in cards if "Souvenir libre" not in c["text"]]
            print(f"STEP4 cards: {json.dumps(cards, ensure_ascii=False)}")
            if len(free_cards) != 1 or len(question_cards) != 1:
                results["tous_shows_both"] = False
                raise RuntimeError("STEP4 failed")
            free_id = free_cards[0]["id"]
            question_id = question_cards[0]["id"]
            results.update(tous_shows_both=True, free_id=free_id, question_id=question_id)
            print(f"STEP4 ok: free_id={free_id} question_id={question_id}")

            # STEP 5: reassign free capsule to Claire
            modal_open = False
            for attempt in range(2):
                el = await page.query_selector(f'[data-testid="capsule-edit-{free_id}"]')
                await el.scroll_into_view_if_needed()
                await page.wait_for_timeout(400)
                await page.click(f'[data-testid="capsule-edit-{free_id}"]', force=True)
                try:
                    await page.wait_for_selector('[data-testid="edit-capsule-title"]', timeout=12000)
                    modal_open = True
                    break
                except Exception:
                    print(f"STEP5 attempt {attempt+1}: modal not open, retry")
                    await page.wait_for_timeout(6500)
            results["edit_modal_opens"] = modal_open
            if not modal_open:
                await page.screenshot(path="/app/test_reports/screens/iter9-modal-fail.jpeg", quality=40)
                raise RuntimeError("edit modal never opened")
            print("STEP5 modal open")
            opt = await page.query_selector(f'[data-testid="edit-capsule-resident-{CLAIRE}"]')
            await opt.scroll_into_view_if_needed()
            await page.wait_for_timeout(500)
            await page.click(f'[data-testid="edit-capsule-resident-{CLAIRE}"]', force=True)
            await page.wait_for_timeout(300)
            await page.click('[data-testid="edit-capsule-save"]', force=True)
            await page.wait_for_timeout(2000)
            print("STEP5b assignment saved")

            # STEP 6: hidden from Tous
            ids_after = [c["id"] for c in await list_cards(page)]
            results["tous_hides_reassigned_free"] = (free_id not in ids_after) and (question_id in ids_after)
            print(f"STEP6 Tous after reassign: {ids_after} -> hidden_ok={results['tous_hides_reassigned_free']}")
            await page.screenshot(path="/app/test_reports/screens/iter9-tous-after-reassign.jpeg", quality=40)

            # STEP 7: search regression
            await page.fill('[data-testid="archive-search"]', "libre")
            await page.wait_for_timeout(800)
            cards_search = await list_cards(page)
            empty_msg = await page.is_visible('text=Aucun souvenir trouvé')
            results["search_hides_reassigned"] = len(cards_search) == 0 and bool(empty_msg)
            print(f"STEP7 search 'libre': cards={len(cards_search)} empty_msg={empty_msg}")
            await page.fill('[data-testid="archive-search"]', "")
            await page.wait_for_timeout(800)
            results["search_clear_restores"] = len(await list_cards(page)) == 1
            print(f"STEP7b cleared restores={results['search_clear_restores']}")

            # STEP 8: Claire filter shows reassigned capsule
            await page.click(f'[data-testid="archive-filter-{CLAIRE}"]', force=True)
            await page.wait_for_timeout(1200)
            ids_claire = [c["id"] for c in await list_cards(page)]
            results["claire_filter_shows_reassigned"] = free_id in ids_claire and question_id in ids_claire
            print(f"STEP8 Claire filter: {ids_claire} -> ok={results['claire_filter_shows_reassigned']}")
            await page.screenshot(path="/app/test_reports/screens/iter9-claire-filter.jpeg", quality=40)

            # STEP 9: play/pause
            el = await page.query_selector(f'[data-testid="capsule-play-{free_id}"]')
            if el:
                await el.scroll_into_view_if_needed()
                await page.click(f'[data-testid="capsule-play-{free_id}"]', force=True)
                await page.wait_for_timeout(1500)
                await page.click(f'[data-testid="capsule-play-{free_id}"]', force=True)
                results["play_pause"] = True
                print("STEP9 play/pause ok")
            else:
                results["play_pause"] = False
                print("STEP9 FAIL no play button")

            # STEP 10: auto transcription
            transcribed = False
            for _ in range(8):
                if await page.query_selector(f'[data-testid="capsule-transcription-{free_id}"]') or await page.query_selector(f'[data-testid="capsule-transcription-{question_id}"]'):
                    transcribed = True
                    break
                await page.wait_for_timeout(5000)
            results["auto_transcription"] = transcribed
            print(f"STEP10 auto-transcription visible={transcribed}")

            # STEP 11: Claire fiche shows reassigned capsule
            await page.click('[data-testid="archive-back"]', force=True)
            await page.wait_for_selector('[data-testid="home-screen"]', timeout=8000)
            await page.click(f'[data-testid="home-profile-{CLAIRE}"]', force=True)
            await page.wait_for_selector('[data-testid="profile-start-workshop"]', timeout=8000)
            await page.wait_for_timeout(1200)
            ids_profile = [c["id"] for c in await list_cards(page)]
            results["profile_shows_reassigned"] = free_id in ids_profile and question_id in ids_profile
            print(f"STEP11 Claire fiche: {ids_profile} -> ok={results['profile_shows_reassigned']}")
            await page.screenshot(path="/app/test_reports/screens/iter9-claire-fiche.jpeg", quality=40)
        except Exception as e:
            print(f"EXCEPTION: {e}")
            try:
                await page.screenshot(path="/app/test_reports/screens/iter9-error.jpeg", quality=40)
            except Exception:
                pass
        finally:
            await browser.close()
    print(f"FINAL RESULTS: {json.dumps(results)}")


asyncio.run(main())
