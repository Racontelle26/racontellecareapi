export type PdfChapter = { id: string; title: string; content: string; memory_count: number };
export type PdfPhoto = { src: string; caption: string };

function escapeHtml(value: string) {
  return (value || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

export function openPrintPreviewWindow() {
  if (typeof window === "undefined") return null;
  const target = window.open("", "_blank", "width=900,height=900");
  if (!target) return null;
  target.document.write("<!doctype html><title>Préparation du livre…</title><p style='font-family:Georgia;padding:40px'>Préparation de votre livre familial…</p>");
  return target;
}

export async function printBookWindow(target: Window, html: string) {
  target.document.open();
  target.document.write(html);
  target.document.close();
  const images = Array.from(target.document.images);
  await Promise.all(images.map((image) => image.complete ? Promise.resolve() : new Promise<void>((resolve) => {
    image.onload = () => resolve();
    image.onerror = () => resolve();
  })));
  await target.document.fonts?.ready;
  const chapterCount = target.document.querySelectorAll("article.chapter").length;
  const contentLengths = Array.from(target.document.querySelectorAll(".chapter-content")).map((node) => node.textContent?.trim().length || 0);
  target.focus();
  target.addEventListener("afterprint", () => target.close(), { once: true });
  target.print();
  return { chapterCount, contentLengths };
}

export function buildBookHtml(familyName: string, date: string, chapters: PdfChapter[], photos: PdfPhoto[]) {
  const stories = chapters.map((chapter, index) => {
    const paragraphs = chapter.content.split(/\n\s*\n/).map((value) => value.replace(/\n/g, " ").trim()).filter(Boolean);
    return `<article class="chapter" data-chapter-id="${escapeHtml(chapter.id)}"><p class="chapter-no">CHAPITRE ${index + 1} · ${chapter.memory_count} SOUVENIRS</p><h2>${escapeHtml(chapter.title)}</h2><div class="chapter-content">${paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join("")}</div></article>`;
  }).join("");
  const gallery = photos.length ? `<section class="gallery"><h2>Album de famille</h2>${photos.map((photo) => `<figure><img src="${photo.src}"/><figcaption>${escapeHtml(photo.caption)}</figcaption></figure>`).join("")}</section>` : "";
  return `<!DOCTYPE html><html><head><meta charset="utf-8"/><title>${escapeHtml(familyName)} — Racontelle</title><style>@page{margin:48px}*{box-sizing:border-box}body{font-family:Georgia,'Times New Roman',serif;color:#3A332C;margin:0}.print-help{padding:14px;background:#F2DADA;text-align:center;font:14px Arial}.cover{text-align:center;padding:150px 0;break-after:page}.brand{color:#B57477;font-size:20px;letter-spacing:3px}.cover h1{font-size:44px;margin:24px 0 8px}.date{color:#8A8177;font-size:14px}.chapter{break-after:page;page-break-after:always}.chapter-no{color:#8A8177;font:11px Arial;letter-spacing:1px}.chapter h2,.gallery h2{color:#B57477;font-size:28px;border-bottom:1px solid #EBE6DC;padding-bottom:10px}.chapter-content p{font-size:15px;line-height:1.75;text-align:justify;orphans:3;widows:3}.gallery figure{display:inline-block;width:46%;margin:2%;vertical-align:top;text-align:center;break-inside:avoid}.gallery img{width:100%;border-radius:8px}.gallery figcaption{font-size:11px;color:#8A8177;margin-top:4px}@media print{.print-help{display:none}body{-webkit-print-color-adjust:exact;print-color-adjust:exact}}</style></head><body data-export-chapter-count="${chapters.length}"><div class="print-help">Choisissez « Enregistrer au format PDF » dans la fenêtre d’impression.</div><div class="cover"><div class="brand">RACONTELLE</div><h1>${escapeHtml(familyName)}</h1><div class="date">Livre de souvenirs · ${escapeHtml(date)}</div></div>${stories}${gallery}</body></html>`;
}