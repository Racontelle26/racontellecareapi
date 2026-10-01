# -*- coding: utf-8 -*-
"""Editorial bank of 400 life-story questions for Racontelle.

Format per line: NUMBER | THEME | TEXT | SENSITIVE(true/false)
The two sensitive themes (Intimité, corps & sexualité, Deuils séparations &
disparitions) are marked sensitive=true and stay inactive/hidden by default.
"""

QUESTIONS_RAW = """1 | Naissance & origines | Que connaissez-vous de votre naissance et des circonstances autour de votre arrivée ? | false
2 | Naissance & origines | Qui vous a raconté votre naissance pour la première fois ? | false
3 | Naissance & origines | Pourquoi vos parents ont-ils choisi votre prénom ? | false
4 | Naissance & origines | Avez-vous un surnom de famille et quelle est son histoire ? | false
5 | Naissance & origines | Où êtes-vous né(e) et que représente ce lieu pour vous ? | false
6 | Naissance & origines | Quels étaient les métiers, habitudes ou traits de caractère de vos parents ? | false
7 | Naissance & origines | Quelles histoires entendiez-vous souvent sur vos grands-parents ? | false
8 | Naissance & origines | Quels objets, photos ou documents racontent le mieux vos origines ? | false
9 | Naissance & origines | Quelle langue, expression ou accent faisait partie de votre famille ? | false
10 | Naissance & origines | Quelles valeurs vos parents voulaient-ils vous transmettre ? | false
11 | Naissance & origines | Y avait-il une légende familiale ou une histoire souvent répétée ? | false
12 | Naissance & origines | Quelle branche de votre famille connaissez-vous le mieux ? | false
13 | Naissance & origines | Quelle branche de votre famille aimeriez-vous mieux connaître ? | false
14 | Naissance & origines | Quel souvenir familial vous relie le plus à vos racines ? | false
15 | Naissance & origines | Comment décririez-vous l’ambiance de votre famille lorsque vous étiez petit(e) ? | false
16 | Naissance & origines | Y avait-il des secrets, des silences ou des sujets dont on parlait peu ? | false
17 | Naissance & origines | Quelle personne de votre famille vous a le plus marqué(e) dès l’enfance ? | false
18 | Naissance & origines | Quelle tradition familiale existait déjà avant votre naissance ? | false
19 | Naissance & origines | Si vous deviez présenter vos origines en trois mots, lesquels choisiriez-vous ? | false
20 | Naissance & origines | Quelle trace de vos origines souhaitez-vous absolument transmettre ? | false
21 | Enfance & premiers souvenirs | Quel est votre tout premier souvenir ? | false
22 | Enfance & premiers souvenirs | À quoi ressemblait votre maison ou appartement d’enfance ? | false
23 | Enfance & premiers souvenirs | Quelle odeur vous ramène immédiatement à votre enfance ? | false
24 | Enfance & premiers souvenirs | Quel bruit ou quelle voix associez-vous à votre enfance ? | false
25 | Enfance & premiers souvenirs | Avec quoi aimiez-vous jouer pendant des heures ? | false
26 | Enfance & premiers souvenirs | Quel était votre jouet ou objet préféré ? | false
27 | Enfance & premiers souvenirs | Quel était votre endroit secret ou refuge ? | false
28 | Enfance & premiers souvenirs | Quel souvenir gardez-vous des vacances quand vous étiez enfant ? | false
29 | Enfance & premiers souvenirs | Quelle bêtise avez-vous faite et dont on reparle encore ? | false
30 | Enfance & premiers souvenirs | De quoi aviez-vous peur enfant ? | false
31 | Enfance & premiers souvenirs | Qu’est-ce qui vous faisait rire aux éclats ? | false
32 | Enfance & premiers souvenirs | Quel adulte vous rassurait le plus ? | false
33 | Enfance & premiers souvenirs | Quel plat ou goûter vous rendait heureux(se) ? | false
34 | Enfance & premiers souvenirs | Quelle était votre chanson, comptine ou histoire préférée ? | false
35 | Enfance & premiers souvenirs | Comment passiez-vous vos mercredis, dimanches ou vacances ? | false
36 | Enfance & premiers souvenirs | Quel enfant étiez-vous : calme, rêveur(se), curieux(se), turbulent(e) ? | false
37 | Enfance & premiers souvenirs | Quel souvenir d’enfance aimeriez-vous revivre une journée ? | false
38 | Enfance & premiers souvenirs | Qu’avez-vous appris très tôt sans vous en rendre compte ? | false
39 | Enfance & premiers souvenirs | Quelle phrase entendiez-vous souvent à la maison ? | false
40 | Enfance & premiers souvenirs | Quel petit détail de votre enfance aimeriez-vous que vos proches connaissent ? | false
41 | Famille & traditions | Quelle place occupait la famille dans votre vie quotidienne ? | false
42 | Famille & traditions | Qui était le pilier de votre famille ? | false
43 | Famille & traditions | Quelle personne réunissait tout le monde ? | false
44 | Famille & traditions | À quoi ressemblaient les repas de famille ? | false
45 | Famille & traditions | Quelle fête familiale était la plus importante ? | false
46 | Famille & traditions | Quelle tradition vous manque aujourd’hui ? | false
47 | Famille & traditions | Quelle tradition avez-vous gardée ou recréée ? | false
48 | Famille & traditions | Comment les conflits se réglaient-ils dans votre famille ? | false
49 | Famille & traditions | Quelle phrase typique résume l’esprit de votre famille ? | false
50 | Famille & traditions | Quel membre de votre famille avait le plus d’humour ? | false
51 | Famille & traditions | Qui racontait les meilleures histoires ? | false
52 | Famille & traditions | Quelle personne vous impressionnait le plus ? | false
53 | Famille & traditions | Quel héritage moral avez-vous reçu de votre famille ? | false
54 | Famille & traditions | Quel objet familial aimeriez-vous conserver ou transmettre ? | false
55 | Famille & traditions | Quelle photo de famille raconte le plus de choses ? | false
56 | Famille & traditions | Y avait-il une recette, une chanson ou une prière familiale ? | false
57 | Famille & traditions | Comment accueillait-on les nouveaux membres dans la famille ? | false
58 | Famille & traditions | Quelle histoire familiale mérite de ne jamais disparaître ? | false
59 | Famille & traditions | Qu’avez-vous compris tardivement sur votre famille ? | false
60 | Famille & traditions | Que souhaiteriez-vous dire aux générations suivantes sur votre famille ? | false
61 | École & études | Quel souvenir gardez-vous de votre premier jour d’école ? | false
62 | École & études | Étiez-vous plutôt heureux(se) ou inquiet(ète) d’aller à l’école ? | false
63 | École & études | Quel professeur vous a le plus marqué(e) ? | false
64 | École & études | Quelle matière aimiez-vous le plus ? | false
65 | École & études | Quelle matière vous semblait impossible ? | false
66 | École & études | Aviez-vous un rituel avant d’aller en classe ? | false
67 | École & études | Quel était votre cartable, trousse ou objet scolaire préféré ? | false
68 | École & études | Quelle récompense ou remarque vous a fait du bien ? | false
69 | École & études | Quelle injustice ou humiliation vous a marqué(e) ? | false
70 | École & études | Quel ami ou camarade d’école n’avez-vous jamais oublié ? | false
71 | École & études | Quelle bêtise avez-vous faite à l’école ? | false
72 | École & études | Quel livre étudié vous a laissé une trace ? | false
73 | École & études | Comment vos parents suivaient-ils votre scolarité ? | false
74 | École & études | Quel métier rêviez-vous de faire enfant ? | false
75 | École & études | Comment avez-vous choisi vos études ou votre orientation ? | false
76 | École & études | Avez-vous regretté un choix scolaire ou professionnel ? | false
77 | École & études | Quelle compétence apprise à l’école vous sert encore ? | false
78 | École & études | Qu’auriez-vous aimé qu’on vous enseigne plus tôt ? | false
79 | École & études | Quel conseil donneriez-vous à un enfant qui n’aime pas l’école ? | false
80 | École & études | Quelle phrase résume votre rapport aux études ? | false
81 | Adolescence & construction de soi | Comment décririez-vous votre adolescence en quelques mots ? | false
82 | Adolescence & construction de soi | Quel était votre style vestimentaire à l’adolescence ? | false
83 | Adolescence & construction de soi | Quelle musique écoutiez-vous en boucle ? | false
84 | Adolescence & construction de soi | Quel poster, objet ou décoration avait une place importante dans votre chambre ? | false
85 | Adolescence & construction de soi | Quelle liberté avez-vous obtenue en premier ? | false
86 | Adolescence & construction de soi | Quelle règle familiale vous semblait injuste ? | false
87 | Adolescence & construction de soi | Quelle personne vous comprenait le mieux à cette période ? | false
88 | Adolescence & construction de soi | Quelle amitié adolescente vous a construit(e) ? | false
89 | Adolescence & construction de soi | Quel complexe ou doute avez-vous traversé ? | false
90 | Adolescence & construction de soi | De quoi étiez-vous fier(ère) à l’adolescence ? | false
91 | Adolescence & construction de soi | Quelle sortie ou soirée n’avez-vous jamais oubliée ? | false
92 | Adolescence & construction de soi | Quel événement vous a fait grandir plus vite ? | false
93 | Adolescence & construction de soi | Comment imaginiez-vous votre vie adulte ? | false
94 | Adolescence & construction de soi | Quelle erreur de jeunesse vous fait sourire aujourd’hui ? | false
95 | Adolescence & construction de soi | Quelle discussion avec vos parents vous a marqué(e) ? | false
96 | Adolescence & construction de soi | Qu’est-ce qui vous donnait envie de vous dépasser ? | false
97 | Adolescence & construction de soi | Quelle valeur personnelle s’est affirmée à cette période ? | false
98 | Adolescence & construction de soi | Quelle part de l’adolescent(e) que vous étiez est encore là aujourd’hui ? | false
99 | Adolescence & construction de soi | Qu’auriez-vous aimé entendre à cette période de votre vie ? | false
100 | Adolescence & construction de soi | Que diriez-vous aujourd’hui à l’adolescent(e) que vous étiez ? | false
101 | Amitiés & relations sociales | Qui a été votre premier grand ami ou votre première grande amie ? | false
102 | Amitiés & relations sociales | Qu’est-ce qui fait une vraie amitié selon vous ? | false
103 | Amitiés & relations sociales | Quelle amitié a traversé le plus d’années ? | false
104 | Amitiés & relations sociales | Quelle rencontre a changé votre vie ? | false
105 | Amitiés & relations sociales | Avec qui avez-vous le plus ri ? | false
106 | Amitiés & relations sociales | Quelle personne a été là dans un moment difficile ? | false
107 | Amitiés & relations sociales | Avez-vous déjà perdu une amitié importante ? | false
108 | Amitiés & relations sociales | Comment entretenez-vous les liens avec les gens que vous aimez ? | false
109 | Amitiés & relations sociales | Êtes-vous plutôt entouré(e) de beaucoup de personnes ou de quelques proches ? | false
110 | Amitiés & relations sociales | Quelle qualité recherchez-vous chez un ami ? | false
111 | Amitiés & relations sociales | Quelle qualité vos amis vous reconnaissent-ils ? | false
112 | Amitiés & relations sociales | Quelle fête, sortie ou voyage entre amis reste mémorable ? | false
113 | Amitiés & relations sociales | Quel ami vous a appris quelque chose d’important ? | false
114 | Amitiés & relations sociales | Quelle amitié improbable avez-vous vécue ? | false
115 | Amitiés & relations sociales | Quelle personne aimeriez-vous remercier aujourd’hui ? | false
116 | Amitiés & relations sociales | À qui aimeriez-vous reparler après des années de silence ? | false
117 | Amitiés & relations sociales | Quelle place a l’amitié dans votre équilibre de vie ? | false
118 | Amitiés & relations sociales | Comment votre façon d’aimer vos amis a-t-elle évolué ? | false
119 | Amitiés & relations sociales | Quel souvenir d’amitié mérite d’être transmis ? | false
120 | Amitiés & relations sociales | Quel conseil donneriez-vous pour garder une belle amitié ? | false
121 | Vie amoureuse & couple | Quand avez-vous connu votre premier grand sentiment amoureux ? | false
122 | Vie amoureuse & couple | Comment avez-vous compris que vous étiez amoureux(se) ? | false
123 | Vie amoureuse & couple | Quelle rencontre amoureuse vous a le plus marqué(e) ? | false
124 | Vie amoureuse & couple | Quel geste romantique n’avez-vous jamais oublié ? | false
125 | Vie amoureuse & couple | Quelle chanson associez-vous à une histoire d’amour ? | false
126 | Vie amoureuse & couple | Qu’est-ce qui vous touche le plus chez une personne ? | false
127 | Vie amoureuse & couple | Qu’avez-vous appris de votre première histoire d’amour ? | false
128 | Vie amoureuse & couple | Avez-vous vécu un amour impossible ou contrarié ? | false
129 | Vie amoureuse & couple | Quelle rupture vous a fait grandir ? | false
130 | Vie amoureuse & couple | Comment votre vision de l’amour a-t-elle changé avec l’âge ? | false
131 | Vie amoureuse & couple | Qu’est-ce qui fait durer un couple selon vous ? | false
132 | Vie amoureuse & couple | Quel compromis important avez-vous appris à faire ? | false
133 | Vie amoureuse & couple | Quelle erreur relationnelle ne referiez-vous pas ? | false
134 | Vie amoureuse & couple | Quel souvenir de couple vous fait encore sourire ? | false
135 | Vie amoureuse & couple | Quelle discussion a été décisive dans votre vie amoureuse ? | false
136 | Vie amoureuse & couple | Qu’est-ce que vous avez appris sur la fidélité, la confiance ou la liberté ? | false
137 | Vie amoureuse & couple | Quelle qualité est indispensable pour aimer longtemps ? | false
138 | Vie amoureuse & couple | Quel conseil donneriez-vous à quelqu’un qui cherche l’amour ? | false
139 | Vie amoureuse & couple | Qu’aimeriez-vous que vos proches comprennent de votre vie amoureuse ? | false
140 | Vie amoureuse & couple | Quelle phrase résume votre expérience de l’amour ? | false
141 | Intimité, corps & sexualité | Comment parlait-on du corps et de l’intimité dans votre famille ? | true
142 | Intimité, corps & sexualité | Quels messages avez-vous reçus sur la pudeur lorsque vous étiez jeune ? | true
143 | Intimité, corps & sexualité | Quand vous êtes-vous senti(e) à l’aise avec votre corps ? | true
144 | Intimité, corps & sexualité | Qu’est-ce que le temps vous a appris sur le désir et la tendresse ? | true
145 | Intimité, corps & sexualité | Quelle place donnez-vous à la confiance dans l’intimité ? | true
146 | Intimité, corps & sexualité | Avez-vous eu le sentiment d’avoir été assez informé(e) sur la sexualité ? | true
147 | Intimité, corps & sexualité | Quel conseil bienveillant auriez-vous aimé recevoir plus jeune ? | true
148 | Intimité, corps & sexualité | Comment votre rapport au corps a-t-il évolué avec les années ? | true
149 | Intimité, corps & sexualité | Quelle différence faites-vous entre attirance, amour et attachement ? | true
150 | Intimité, corps & sexualité | Qu’avez-vous appris sur le respect de soi dans les relations intimes ? | true
151 | Intimité, corps & sexualité | Quelle importance accordez-vous au consentement et à la liberté de chacun ? | true
152 | Intimité, corps & sexualité | Avez-vous déjà dû apprendre à poser vos limites ? | true
153 | Intimité, corps & sexualité | Quelle croyance sur la sexualité avez-vous remise en question ? | true
154 | Intimité, corps & sexualité | Comment les époques ont-elles influencé la manière de parler d’intimité ? | true
155 | Intimité, corps & sexualité | Qu’est-ce qui vous semble essentiel à transmettre sur le respect du corps ? | true
156 | Intimité, corps & sexualité | Quelle place la tendresse a-t-elle eue dans votre vie ? | true
157 | Intimité, corps & sexualité | Qu’est-ce qui rend une relation intime belle et juste selon vous ? | true
158 | Intimité, corps & sexualité | Avez-vous connu des tabous familiaux autour de ce sujet ? | true
159 | Intimité, corps & sexualité | Quel regard portez-vous aujourd’hui sur votre parcours intime ? | true
160 | Intimité, corps & sexualité | Quel message respectueux aimeriez-vous transmettre aux jeunes générations ? | true
161 | Premier job & parcours professionnel | Quel a été votre tout premier travail rémunéré ? | false
162 | Premier job & parcours professionnel | Quel souvenir gardez-vous de votre premier salaire ? | false
163 | Premier job & parcours professionnel | Qu’avez-vous acheté avec votre premier argent gagné ? | false
164 | Premier job & parcours professionnel | Qui vous a appris la valeur du travail ? | false
165 | Premier job & parcours professionnel | Quel métier vouliez-vous faire au départ ? | false
166 | Premier job & parcours professionnel | Comment avez-vous trouvé votre premier emploi ? | false
167 | Premier job & parcours professionnel | Quel patron, collègue ou client vous a marqué(e) ? | false
168 | Premier job & parcours professionnel | Quelle erreur professionnelle vous a beaucoup appris ? | false
169 | Premier job & parcours professionnel | Quel moment vous a donné confiance dans vos capacités ? | false
170 | Premier job & parcours professionnel | Quel travail était difficile mais formateur ? | false
171 | Premier job & parcours professionnel | Quelle compétence avez-vous apprise sur le terrain ? | false
172 | Premier job & parcours professionnel | Avez-vous déjà changé complètement de voie ? | false
173 | Premier job & parcours professionnel | Quelle décision professionnelle a été déterminante ? | false
174 | Premier job & parcours professionnel | Quel métier exercé mérite d’être raconté ? | false
175 | Premier job & parcours professionnel | Quelle journée de travail n’avez-vous jamais oubliée ? | false
176 | Premier job & parcours professionnel | Qu’est-ce qui vous motivait le plus dans le travail ? | false
177 | Premier job & parcours professionnel | Qu’est-ce qui vous pesait le plus dans le travail ? | false
178 | Premier job & parcours professionnel | Quelle fierté professionnelle voulez-vous transmettre ? | false
179 | Premier job & parcours professionnel | Quel conseil donneriez-vous à quelqu’un qui commence sa carrière ? | false
180 | Premier job & parcours professionnel | Quelle phrase résume votre parcours professionnel ? | false
181 | Travail, réussites & échecs | De quelle réussite êtes-vous le plus fier(ère) ? | false
182 | Travail, réussites & échecs | Quel échec vous a finalement rendu plus fort(e) ? | false
183 | Travail, réussites & échecs | Avez-vous déjà osé recommencer après une déception ? | false
184 | Travail, réussites & échecs | Quelle responsabilité vous a fait grandir ? | false
185 | Travail, réussites & échecs | Quel projet vous a demandé beaucoup de courage ? | false
186 | Travail, réussites & échecs | Quelle reconnaissance professionnelle vous a touché(e) ? | false
187 | Travail, réussites & échecs | Quel conflit au travail vous a appris quelque chose ? | false
188 | Travail, réussites & échecs | Comment gérez-vous la pression ou les imprévus ? | false
189 | Travail, réussites & échecs | Qu’est-ce que vous faites mieux que la plupart des gens ? | false
190 | Travail, réussites & échecs | Quelle valeur ne voulez-vous jamais sacrifier au travail ? | false
191 | Travail, réussites & échecs | Avez-vous connu une période de doute professionnel ? | false
192 | Travail, réussites & échecs | Qui vous a ouvert une porte ou fait confiance ? | false
193 | Travail, réussites & échecs | Quel risque professionnel avez-vous pris ? | false
194 | Travail, réussites & échecs | Qu’est-ce qui vous a donné envie d’entreprendre, de créer ou de transmettre ? | false
195 | Travail, réussites & échecs | Comment définissez-vous la réussite ? | false
196 | Travail, réussites & échecs | Qu’avez-vous appris sur l’argent grâce au travail ? | false
197 | Travail, réussites & échecs | Quel équilibre avez-vous cherché entre vie privée et travail ? | false
198 | Travail, réussites & échecs | Quel talent aimeriez-vous que vos proches retiennent de vous ? | false
199 | Travail, réussites & échecs | Quelle décision professionnelle referiez-vous sans hésiter ? | false
200 | Travail, réussites & échecs | Quelle leçon de travail souhaitez-vous transmettre ? | false
201 | Maison, lieux de vie & quotidien | Quel lieu avez-vous appelé “chez moi” avec le plus d’émotion ? | false
202 | Maison, lieux de vie & quotidien | À quoi ressemblait votre maison idéale quand vous étiez jeune ? | false
203 | Maison, lieux de vie & quotidien | Quelle pièce de la maison vous a le plus marqué(e) ? | false
204 | Maison, lieux de vie & quotidien | Quel objet du quotidien raconte votre histoire ? | false
205 | Maison, lieux de vie & quotidien | Quel déménagement a changé votre vie ? | false
206 | Maison, lieux de vie & quotidien | Quel quartier, village ou ville a compté pour vous ? | false
207 | Maison, lieux de vie & quotidien | Quel souvenir associez-vous à votre cuisine ? | false
208 | Maison, lieux de vie & quotidien | Quel souvenir associez-vous à votre jardin, balcon ou extérieur ? | false
209 | Maison, lieux de vie & quotidien | Quelle maison aimeriez-vous revoir une dernière fois ? | false
210 | Maison, lieux de vie & quotidien | Quel bruit de maison vous manque ? | false
211 | Maison, lieux de vie & quotidien | Quelle routine du matin ou du soir vous ressemble ? | false
212 | Maison, lieux de vie & quotidien | Quel rituel familial se passait toujours à la maison ? | false
213 | Maison, lieux de vie & quotidien | Qu’est-ce qui rend un foyer chaleureux selon vous ? | false
214 | Maison, lieux de vie & quotidien | Avez-vous déjà construit, rénové ou aménagé un lieu important ? | false
215 | Maison, lieux de vie & quotidien | Quelle décoration ou couleur vous représente ? | false
216 | Maison, lieux de vie & quotidien | Quel souvenir gardez-vous des voisins ou de la vie de quartier ? | false
217 | Maison, lieux de vie & quotidien | Quelle maison vous a donné un sentiment de sécurité ? | false
218 | Maison, lieux de vie & quotidien | Quel lieu raconte le mieux une période de votre vie ? | false
219 | Maison, lieux de vie & quotidien | Qu’aimeriez-vous transmettre de votre façon d’habiter le monde ? | false
220 | Maison, lieux de vie & quotidien | Si votre maison pouvait parler, que raconterait-elle ? | false
221 | Animaux & nature | Avez-vous grandi avec des animaux ? | false
222 | Animaux & nature | Quel animal a le plus compté dans votre vie ? | false
223 | Animaux & nature | Quelle histoire drôle ou tendre avez-vous vécue avec un animal ? | false
224 | Animaux & nature | Avez-vous déjà eu peur d’un animal ? | false
225 | Animaux & nature | Quel paysage vous apaise immédiatement ? | false
226 | Animaux & nature | Quelle saison préférez-vous et pourquoi ? | false
227 | Animaux & nature | Quel souvenir avez-vous de la campagne, de la mer, de la montagne ou de la forêt ? | false
228 | Animaux & nature | Avez-vous déjà cultivé un jardin, un potager ou des plantes ? | false
229 | Animaux & nature | Quelle plante, fleur ou arbre vous rappelle quelqu’un ? | false
230 | Animaux & nature | Quel rapport avez-vous avec la nature aujourd’hui ? | false
231 | Animaux & nature | Quelle promenade n’avez-vous jamais oubliée ? | false
232 | Animaux & nature | Quel animal sauvage vous fascine ? | false
233 | Animaux & nature | Quelle leçon la nature vous a-t-elle apprise ? | false
234 | Animaux & nature | Quel lieu naturel aimeriez-vous faire découvrir à vos proches ? | false
235 | Animaux & nature | Comment votre rapport aux animaux a-t-il évolué ? | false
236 | Animaux & nature | Avez-vous déjà sauvé, recueilli ou soigné un animal ? | false
237 | Animaux & nature | Quelle odeur de nature vous ramène à un souvenir précis ? | false
238 | Animaux & nature | Quel son naturel aimez-vous entendre ? | false
239 | Animaux & nature | Quelle habitude écologique ou de bon sens avez-vous gardée ? | false
240 | Animaux & nature | Quel souvenir de nature aimeriez-vous transmettre ? | false
241 | Voyages & découvertes | Quel a été votre premier voyage marquant ? | false
242 | Voyages & découvertes | Quelle destination vous a le plus émerveillé(e) ? | false
243 | Voyages & découvertes | Quel voyage a changé votre regard sur la vie ? | false
244 | Voyages & découvertes | Quelle rencontre en voyage n’avez-vous jamais oubliée ? | false
245 | Voyages & découvertes | Quel plat découvert ailleurs vous a marqué(e) ? | false
246 | Voyages & découvertes | Quel paysage vous a coupé le souffle ? | false
247 | Voyages & découvertes | Avez-vous déjà voyagé seul(e) ? | false
248 | Voyages & découvertes | Quel voyage en famille reste le plus précieux ? | false
249 | Voyages & découvertes | Quelle mésaventure de voyage racontez-vous encore ? | false
250 | Voyages & découvertes | Quel endroit aimeriez-vous revoir ? | false
251 | Voyages & découvertes | Quel pays ou région rêvez-vous encore de découvrir ? | false
252 | Voyages & découvertes | Quel souvenir avez-vous des moyens de transport de votre époque ? | false
253 | Voyages & découvertes | Quel voyage vous a appris la patience ? | false
254 | Voyages & découvertes | Quel voyage vous a appris la liberté ? | false
255 | Voyages & découvertes | Quel objet rapporté de voyage gardez-vous ? | false
256 | Voyages & découvertes | Quelle odeur, couleur ou musique associez-vous à un lieu visité ? | false
257 | Voyages & découvertes | Quelle ville vous ressemble le plus ? | false
258 | Voyages & découvertes | Quel conseil donneriez-vous pour bien voyager ? | false
259 | Voyages & découvertes | Que recherchez-vous quand vous partez ailleurs ? | false
260 | Voyages & découvertes | Quel voyage aimeriez-vous raconter à vos descendants ? | false
261 | Lectures, musées & culture | Quel livre vous a marqué durablement ? | false
262 | Lectures, musées & culture | Qui vous a donné le goût de lire ? | false
263 | Lectures, musées & culture | Quel personnage de roman vous a accompagné(e) ? | false
264 | Lectures, musées & culture | Quel livre aimeriez-vous faire lire à vos proches ? | false
265 | Lectures, musées & culture | Quelle phrase ou citation vous revient souvent ? | false
266 | Lectures, musées & culture | Avez-vous fréquenté des bibliothèques, librairies ou clubs de lecture ? | false
267 | Lectures, musées & culture | Quel musée vous a le plus impressionné(e) ? | false
268 | Lectures, musées & culture | Quelle œuvre d’art vous a ému(e) ? | false
269 | Lectures, musées & culture | Quel monument ou lieu culturel vous a marqué(e) ? | false
270 | Lectures, musées & culture | Quel sujet aimez-vous apprendre encore aujourd’hui ? | false
271 | Lectures, musées & culture | Quelle découverte culturelle a changé votre regard ? | false
272 | Lectures, musées & culture | Avez-vous déjà collectionné des livres, cartes, timbres, objets ou souvenirs ? | false
273 | Lectures, musées & culture | Quel journal, magazine ou émission suiviez-vous régulièrement ? | false
274 | Lectures, musées & culture | Quelle période historique vous fascine ? | false
275 | Lectures, musées & culture | Quelle exposition aimeriez-vous revoir ? | false
276 | Lectures, musées & culture | Quel artiste, auteur ou penseur vous inspire ? | false
277 | Lectures, musées & culture | Comment votre curiosité a-t-elle évolué avec le temps ? | false
278 | Lectures, musées & culture | Quel savoir aimeriez-vous transmettre ? | false
279 | Lectures, musées & culture | Quelle activité culturelle vous fait vous sentir vivant(e) ? | false
280 | Lectures, musées & culture | Quelle place la culture a-t-elle eue dans votre vie ? | false
281 | Musique, cinéma & arts | Quelle chanson vous ramène immédiatement à une période de votre vie ? | false
282 | Musique, cinéma & arts | Quel artiste avez-vous le plus écouté ? | false
283 | Musique, cinéma & arts | Quel disque, cassette, CD ou playlist a compté pour vous ? | false
284 | Musique, cinéma & arts | Savez-vous jouer d’un instrument ou auriez-vous aimé apprendre ? | false
285 | Musique, cinéma & arts | Quelle musique passait souvent à la maison ? | false
286 | Musique, cinéma & arts | Quel concert ou spectacle n’avez-vous jamais oublié ? | false
287 | Musique, cinéma & arts | Quel film vous a profondément marqué(e) ? | false
288 | Musique, cinéma & arts | Quel film vous fait toujours rire ou pleurer ? | false
289 | Musique, cinéma & arts | Quelle émission de télévision faisait partie de votre quotidien ? | false
290 | Musique, cinéma & arts | Quel acteur, chanteur ou artiste admiriez-vous ? | false
291 | Musique, cinéma & arts | Avez-vous déjà chanté, dansé, peint, écrit ou joué sur scène ? | false
292 | Musique, cinéma & arts | Quelle activité artistique vous a aidé(e) à vous exprimer ? | false
293 | Musique, cinéma & arts | Quelle chanson aimeriez-vous associer à votre histoire ? | false
294 | Musique, cinéma & arts | Quelle musique aimeriez-vous transmettre à vos enfants ou petits-enfants ? | false
295 | Musique, cinéma & arts | Quel souvenir associez-vous à la radio ? | false
296 | Musique, cinéma & arts | Quel souvenir associez-vous au cinéma ? | false
297 | Musique, cinéma & arts | Quelle œuvre vous apaise ? | false
298 | Musique, cinéma & arts | Quelle œuvre vous donne de l’énergie ? | false
299 | Musique, cinéma & arts | Que dit votre goût artistique de votre personnalité ? | false
300 | Musique, cinéma & arts | Si votre vie avait une bande-son, quelle chanson l’ouvrirait ? | false
301 | Cuisine, restaurants & recettes | Quel plat vous rappelle votre enfance ? | false
302 | Cuisine, restaurants & recettes | Qui cuisinait le plus dans votre famille ? | false
303 | Cuisine, restaurants & recettes | Quelle recette familiale faut-il absolument conserver ? | false
304 | Cuisine, restaurants & recettes | Quel parfum de cuisine vous rend nostalgique ? | false
305 | Cuisine, restaurants & recettes | Quel était le plat du dimanche ou des fêtes ? | false
306 | Cuisine, restaurants & recettes | Quelle recette savez-vous faire sans regarder de livre ? | false
307 | Cuisine, restaurants & recettes | Quel ingrédient vous rappelle quelqu’un ? | false
308 | Cuisine, restaurants & recettes | Quel restaurant vous a marqué(e) ? | false
309 | Cuisine, restaurants & recettes | Quel repas a été particulièrement heureux ? | false
310 | Cuisine, restaurants & recettes | Quel repas a été raté mais mémorable ? | false
311 | Cuisine, restaurants & recettes | Quel dessert vous faisait plaisir enfant ? | false
312 | Cuisine, restaurants & recettes | Quel plat avez-vous découvert tardivement ? | false
313 | Cuisine, restaurants & recettes | Quel goût n’aimiez-vous pas avant et aimez-vous maintenant ? | false
314 | Cuisine, restaurants & recettes | Quel plat préparez-vous pour faire plaisir ? | false
315 | Cuisine, restaurants & recettes | Quelle boisson ou infusion accompagne vos souvenirs ? | false
316 | Cuisine, restaurants & recettes | Quelle histoire se raconte toujours autour d’une table ? | false
317 | Cuisine, restaurants & recettes | Quel marché, boulangerie ou commerce de bouche a compté pour vous ? | false
318 | Cuisine, restaurants & recettes | Quel repas aimeriez-vous partager encore une fois avec une personne disparue ? | false
319 | Cuisine, restaurants & recettes | Quelle recette aimeriez-vous transmettre avec votre voix ? | false
320 | Cuisine, restaurants & recettes | Si vous deviez créer le menu de votre vie, qu’y mettriez-vous ? | false
321 | Loisirs, passions & associations | Quelle passion vous accompagne depuis longtemps ? | false
322 | Loisirs, passions & associations | Quelle activité vous fait oublier le temps ? | false
323 | Loisirs, passions & associations | Quel loisir avez-vous découvert par hasard ? | false
324 | Loisirs, passions & associations | Quelle activité auriez-vous aimé pratiquer plus tôt ? | false
325 | Loisirs, passions & associations | Avez-vous fait partie d’un club, groupe ou association ? | false
326 | Loisirs, passions & associations | Quel engagement bénévole vous a marqué(e) ? | false
327 | Loisirs, passions & associations | Quelle cause vous touche particulièrement ? | false
328 | Loisirs, passions & associations | Quel talent manuel, sportif ou créatif possédez-vous ? | false
329 | Loisirs, passions & associations | Quelle activité partagée avec d’autres vous a donné de la joie ? | false
330 | Loisirs, passions & associations | Quel loisir vous a aidé(e) dans une période difficile ? | false
331 | Loisirs, passions & associations | Quelle collection, habitude ou passion étonne les autres ? | false
332 | Loisirs, passions & associations | Avez-vous transmis une passion à quelqu’un ? | false
333 | Loisirs, passions & associations | Qui vous a transmis une passion ? | false
334 | Loisirs, passions & associations | Quelle activité aimeriez-vous reprendre ? | false
335 | Loisirs, passions & associations | Quelle activité vous rend fier(ère) de vos progrès ? | false
336 | Loisirs, passions & associations | Qu’est-ce qui vous donne envie de vous investir pour les autres ? | false
337 | Loisirs, passions & associations | Quel souvenir associatif ou collectif mérite d’être raconté ? | false
338 | Loisirs, passions & associations | Quelle passion reflète le mieux votre personnalité ? | false
339 | Loisirs, passions & associations | Que vous reste-t-il à apprendre par plaisir ? | false
340 | Loisirs, passions & associations | Quelle place le jeu, le sport ou la créativité ont-ils dans votre vie ? | false
341 | Deuils, séparations & disparitions | Quelle personne disparue pensez-vous encore souvent ? | true
342 | Deuils, séparations & disparitions | Quel souvenir doux gardez-vous d’elle ou de lui ? | true
343 | Deuils, séparations & disparitions | Quelle voix aimeriez-vous pouvoir réentendre ? | true
344 | Deuils, séparations & disparitions | Quel objet vous relie à une personne disparue ? | true
345 | Deuils, séparations & disparitions | Quelle phrase d’un proche disparu vous accompagne encore ? | true
346 | Deuils, séparations & disparitions | Comment votre famille parlait-elle de la mort ou du deuil ? | true
347 | Deuils, séparations & disparitions | Quelle séparation a été difficile à vivre ? | true
348 | Deuils, séparations & disparitions | Qu’est-ce qui vous a aidé(e) à traverser une perte ? | true
349 | Deuils, séparations & disparitions | Quelle personne vous a soutenu(e) dans un moment de deuil ? | true
350 | Deuils, séparations & disparitions | Quel rituel vous aide à vous souvenir ? | true
351 | Deuils, séparations & disparitions | Quelle musique, odeur ou lieu réveille un souvenir de deuil ? | true
352 | Deuils, séparations & disparitions | Y a-t-il une histoire que vous regrettez de ne pas avoir demandée ? | true
353 | Deuils, séparations & disparitions | Qu’aimeriez-vous encore dire à une personne disparue ? | true
354 | Deuils, séparations & disparitions | Qu’avez-vous appris sur la fragilité de la vie ? | true
355 | Deuils, séparations & disparitions | Comment le deuil a-t-il transformé vos priorités ? | true
356 | Deuils, séparations & disparitions | Quelle trace souhaitez-vous laisser à ceux qui vous aiment ? | true
357 | Deuils, séparations & disparitions | Comment aimeriez-vous que l’on parle de vous plus tard ? | true
358 | Deuils, séparations & disparitions | Quel message de réconfort donneriez-vous à quelqu’un qui perd un proche ? | true
359 | Deuils, séparations & disparitions | Quel souvenir voulez-vous préserver pour qu’il ne s’efface pas ? | true
360 | Deuils, séparations & disparitions | Quelle leçon de vie une personne disparue vous a-t-elle laissée ? | true
361 | Histoire, époque & grands événements | Quel grand événement historique avez-vous vécu de près ou de loin ? | false
362 | Histoire, époque & grands événements | Où étiez-vous lorsque vous avez appris cet événement ? | false
363 | Histoire, époque & grands événements | Quel événement mondial a changé votre vision du monde ? | false
364 | Histoire, époque & grands événements | Quel événement local ou familial a marqué votre génération ? | false
365 | Histoire, époque & grands événements | Quelle invention a le plus transformé votre quotidien ? | false
366 | Histoire, époque & grands événements | Comment votre vie a-t-elle changé avec l’arrivée d’Internet ou du téléphone portable ? | false
367 | Histoire, époque & grands événements | Quel souvenir gardez-vous de la radio, de la télévision ou des journaux ? | false
368 | Histoire, époque & grands événements | Quel événement politique vous a marqué(e) ? | false
369 | Histoire, époque & grands événements | Quel changement de société vous semble le plus important ? | false
370 | Histoire, époque & grands événements | Quelle époque avez-vous préférée vivre ? | false
371 | Histoire, époque & grands événements | Quelle époque vous a semblé plus difficile ? | false
372 | Histoire, époque & grands événements | Comment décririez-vous l’ambiance du monde lorsque vous étiez jeune ? | false
373 | Histoire, époque & grands événements | Quel progrès vous rend optimiste ? | false
374 | Histoire, époque & grands événements | Quel changement vous inquiète ? | false
375 | Histoire, époque & grands événements | Quel événement sportif ou culturel collectif avez-vous vécu avec émotion ? | false
376 | Histoire, époque & grands événements | Quelle crise avez-vous traversée personnellement ou familialement ? | false
377 | Histoire, époque & grands événements | Qu’est-ce que votre génération a appris aux suivantes ? | false
378 | Histoire, époque & grands événements | Qu’est-ce que les jeunes générations vous apprennent ? | false
379 | Histoire, époque & grands événements | Quel souvenir historique aimeriez-vous raconter avec vos mots ? | false
380 | Histoire, époque & grands événements | Quelle trace de votre époque voulez-vous transmettre ? | false
381 | Rêves, philosophie, avenir & transmission | De quoi rêviez-vous enfant ? | false
382 | Rêves, philosophie, avenir & transmission | Quels rêves avez-vous réalisés ? | false
383 | Rêves, philosophie, avenir & transmission | Quel rêve avez-vous abandonné et pourquoi ? | false
384 | Rêves, philosophie, avenir & transmission | Quel rêve gardez-vous encore aujourd’hui ? | false
385 | Rêves, philosophie, avenir & transmission | Qu’est-ce qui donne du sens à votre vie ? | false
386 | Rêves, philosophie, avenir & transmission | Quelle valeur est non négociable pour vous ? | false
387 | Rêves, philosophie, avenir & transmission | Qu’est-ce qui vous rend profondément heureux(se) ? | false
388 | Rêves, philosophie, avenir & transmission | Qu’est-ce qui vous apaise lorsque tout devient difficile ? | false
389 | Rêves, philosophie, avenir & transmission | Quelle grande leçon la vie vous a-t-elle apprise ? | false
390 | Rêves, philosophie, avenir & transmission | Quelle erreur vous a rendu plus sage ? | false
391 | Rêves, philosophie, avenir & transmission | Quelle qualité aimeriez-vous transmettre ? | false
392 | Rêves, philosophie, avenir & transmission | Quelle peur avez-vous dépassée ? | false
393 | Rêves, philosophie, avenir & transmission | Quelle liberté avez-vous conquise ? | false
394 | Rêves, philosophie, avenir & transmission | Qu’aimeriez-vous encore apprendre ? | false
395 | Rêves, philosophie, avenir & transmission | Quel conseil donneriez-vous aux générations suivantes ? | false
396 | Rêves, philosophie, avenir & transmission | Que souhaitez-vous que vos proches retiennent de vous ? | false
397 | Rêves, philosophie, avenir & transmission | Quel message aimeriez-vous enregistrer pour votre famille ? | false
398 | Rêves, philosophie, avenir & transmission | Si vous pouviez laisser trois phrases à ceux que vous aimez, quelles seraient-elles ? | false
399 | Rêves, philosophie, avenir & transmission | Comment aimeriez-vous que Racontelle conserve votre histoire ? | false
400 | Rêves, philosophie, avenir & transmission | Quelle question aimeriez-vous que l’on vous pose mais que personne ne vous a encore posée ? | false"""


def parse_questions():
    items = []
    for line in QUESTIONS_RAW.strip().splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 4:
            continue
        num, theme, text, sensitive = parts
        items.append(
            {
                "source_number": int(num),
                "theme": theme,
                "text": text,
                "sensitive": sensitive.lower() == "true",
                "active": sensitive.lower() != "true",
            }
        )
    return items


THEMES_ORDER = [
    "Naissance & origines",
    "Enfance & premiers souvenirs",
    "Famille & traditions",
    "École & études",
    "Adolescence & construction de soi",
    "Amitiés & relations sociales",
    "Vie amoureuse & couple",
    "Intimité, corps & sexualité",
    "Premier job & parcours professionnel",
    "Travail, réussites & échecs",
    "Maison, lieux de vie & quotidien",
    "Animaux & nature",
    "Voyages & découvertes",
    "Lectures, musées & culture",
    "Musique, cinéma & arts",
    "Cuisine, restaurants & recettes",
    "Loisirs, passions & associations",
    "Deuils, séparations & disparitions",
    "Histoire, époque & grands événements",
    "Rêves, philosophie, avenir & transmission",
]
