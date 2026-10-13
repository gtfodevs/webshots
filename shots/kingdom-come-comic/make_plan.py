"""Builds the Kingdom Come comic plan: draft spec + plan.md + prompts.json (planning only, no art)."""
import json, bisect, os
REPO = '/workspace/webshots-upstream'
TL = json.load(open(f'{REPO}/shots/kingdom-come-16bit/stage/timeline.json'))
B, DB = TL['beats'], TL['downbeats']
END = TL['duration']

def snap(t):
    return min(B, key=lambda b: abs(b - t))
def next_beat(t):
    return B[bisect.bisect_right(B, t + 0.05)]

CAST = {
 'uno': "Uno: chrome robot hero, smooth round chrome head with no face plate seams, glowing red eyes, round chrome headphone ears, long purple fur coat, gold chain with a big gold number-one pendant",
 'aura': "Aura: graceful chrome robot lady, long dark hair with crimson streaks, glowing red eyes, round chrome headphone ears, modest crimson armored outfit with high collar and long sleeves, cyan magic glow in her hands",
 'wizard': "the Wizard: tall silver chrome robot wizard, red eyes, chrome headphone ears under a tall purple star-pattern hat, long silver beard made of fine chrome wire, violet robe, crystal-topped staff",
 'jester': "the Jester: small bouncy silver chrome robot jester, red eyes, chrome headphone ears, magenta-and-teal diamond suit, three-pointed hat with bells, curly-toed shoes",
 'knight': "the Knights: silver chrome robot knights, red eye slits, chrome headphone ears on the helmet, red plume, kite shields, spears, each knight a slightly different helmet crest",
 'sorcerer': "the Horned Sorcerer: tall dark-chrome robot sorcerer, glowing red eyes, curling chrome horns, chrome headphone ears, black-and-purple cape, staff topped with a purple orb",
 'wolf': "chrome robot wolves, segmented silver plates, red eyes, small chrome headphone ears, each wolf with different markings",
 'spider': "chrome robot spiders, round silver bodies, eight jointed legs, cluster of red eyes, tiny chrome headphone ears",
 'bat': "chrome robot bats, silver membrane wings, red eyes, tiny chrome headphone ears",
 'dragon': "the Dragon: big friendly silver chrome robot dragon, red eyes, chrome headphone ears behind the horns, segmented wings, purple glow in its throat",
 'crowd': "crowd of chrome robot townsfolk dancers, red eyes, chrome headphone ears, each with a unique outfit (scarves, aprons, capes, hats) in purple, crimson, teal and gold",
}
STYLE = ("{shot} of {action}, {setting}. 1990s American superhero comic book panel, bold black ink outlines, heavy spot blacks, "
         "cel-shaded flat colour with halftone dot shading, dynamic foreshortening, speed lines, dramatic {light}, playful kid-friendly "
         "adventure tone, early-90s comic energy, 16:9 panel, full bleed. NO text, no lettering, no speech balloons, no sound effects, "
         "no logos, no signatures, no panel borders. Characters: {chars}.")
MOTION = ("Animate this comic panel. {move}. Subtle secondary motion: {sec}. Camera: {cam}. Keep the exact comic art style, ink lines "
          "and colours, keep faces and hands unchanged, same number of arms and fingers, no new characters, no morphing, no text, no cuts.")

# lyric lines (song seconds). Times from timeline.json; lines the aligner missed are marked est.
LYR = [(0.0,"KINGDOM COME, KINGDOM COME"),(4.18,"HEAR THE PULSE OF MY DRUM"),(7.8,"RIGHTEOUS FIRE IN MY SOUL"),(11.7,"GONNA MAKE THE BROKEN WHOLE"),
 (15.12,"KINGDOM COME, KINGDOM COME"),(18.54,"HEAR THE PULSE OF MY DRUM"),(22.3,"RIGHTEOUS FIRE IN MY SOUL"),
 (27.32,"FROM THE SHADOWED PEAKS WHERE DRAGONS SLEEP, I ROAM"),(31.16,"THROUGH ANCIENT FORESTS, MAKING EVIL FLEE MY HOME"),
 (34.78,"WITH ENCHANTED BLADE AND COURAGE BRIGHT, I STAND"),(38.36,"A SHIELD FOR THE WEAK, ACROSS THIS MYSTIC LAND"),
 (42.32,"KINGDOM COME, KINGDOM COME"),(46.09,"FEEL THE THRUM OF MY DRUM"),(51.3,"RIGHTEOUS FIRE IN MY SOUL"),(54.4,"GONNA HELP THE BROKEN WHOLE"),
 (55.68,"BEASTS OF NIGHTMARE, MAGIC DARK, THEY FALL BEFORE MY MIGHT"),(59.58,"EVERY STEP A LEGEND, BLAZING THROUGH THE NIGHT"),
 (63.06,"FOR THE INNOCENT, I FIGHT, WITH A WARRIOR'S GRACE"),(66.46,"BRINGING DAWN TO DARKNESS, LEAVING NO TRACE"),
 (71.14,"KINGDOM COME, KINGDOM COME"),(74.72,"HEAR THE BEAT OF MY DRUM"),(78.84,"HOLY FIRE IN MY BONES"),(81.39,"GONNA MAKE THE BROKEN WHOLE"),
 (84.52,"ACROSS THE PLAINS OF PERIL, WHERE THE WICKED PLOTS RESIDE"),(87.78,"MY SPIRIT'S AN ARROW, PIERCING THROUGH THEIR PRIDE"),
 (91.42,"WITH SPELLS UNBOUND, AND ANCIENT OATHS I KEEP"),(95.53,"THE REALM'S PROTECTOR, WHILE THE FEARFUL SLEEP"),
 (99.36,"KINGDOM COME, KINGDOM COME"),(103.6,"HEAR THE BEAT OF MY DRUM"),(106.66,"RIGHTEOUS FIRE IN MY SOUL"),(110.86,"GONNA MAKE THE SHATTERED WHOLE"),
 (112.22,"FROM FORGOTTEN RUINS TO THE WIZARD'S CURSED LAIR"),(116.66,"I FACE THE UNKNOWN, WITHOUT A SINGLE FEAR"),
 (119.8,"A BEACON OF JUSTICE, AGAINST THE CREEPING DREAD"),(123.04,"RESTORING BALANCE, UNTIL ALL EVIL'S BLED"),
 (128.38,"KINGDOM COME, KINGDOM COME"),(131.58,"HEAR THE BEAT OF MY DRUM"),(134.58,"RIGHTEOUS FIRE IN MY SOUL")]
EST = {46.09, 81.39, 95.53, 116.66}

# pages: (id, start downbeat, end downbeat or None=song end, location, [panels]); panel = (db, slot|'splash', fields)
P = lambda **k: k
PAGES = [
 ('page01', 0, 8, 'chorus 1 - the kingdom', [
  (0, 'top-left', P(id='p01', loc='castle gate', cam='wide establishing shot', moment='arrival',
     shot='Wide establishing shot', action='Uno and Aura walking up to a giant chrome castle gate at dawn, waving at a tiny chrome robot guard who salutes too hard and wobbles',
     setting='shining chrome kingdom on a hill, purple and gold banners, crystal spires', light='sunrise gold and magenta rim light',
     refs=['uno','aura','knight'], move='Uno and Aura stride toward the gate, the little guard wobbles from his salute', sec='banners ripple, glints run along the spires', cam_m='slow push-in', exp=2.0)),
  (2, 'top-right', P(id='p02', loc='castle gate', cam='low angle', moment='drum call',
     shot='Low-angle shot', action='Uno swinging two glowing mallets at a huge round chrome war drum mounted on the gate tower, rings of cyan sound bursting out, Aura covering her headphone ears with a grin',
     setting='top of the castle gate tower, sky full of morning clouds', light='cyan sound-wave glow and warm sun',
     refs=['uno','aura'], move='Uno brings both mallets down on the drum, a ring of cyan light pulses out', sec='coat fur ruffles, clouds drift', cam_m='locked off', exp=1.8,
     sfx=('BOOM!', [0.74, 0.22], 6, [255, 214, 0]))),
  (6, 'splash', P(id='s03', loc='castle courtyard', cam='heroic high-angle splash', moment='mending the crest',
     shot='Full splash, high angle looking down', action='Aura casting a spiral of cyan magic that mends a cracked giant chrome kingdom crest on the courtyard floor while Uno and a cheering crowd of robot townsfolk throw confetti',
     setting='castle courtyard with fountains and purple flags', light='cyan magic glow and golden confetti sparkle',
     refs=['aura','uno','crowd'], move='the cyan spiral sweeps around the crest and the crack seals with a flash', sec='confetti falls, crowd arms wave', cam_m='slow pull-back', exp=2.2,
     sfx=('SHWING!', [0.78, 0.8], -6, [90, 230, 255]))),
 ]),
 ('page02', 8, 15, 'chorus 1 reprise - the quest', [
  (8, 'top-left', P(id='p04', loc="wizard's library", cam='over-the-shoulder', moment='the quest map',
     shot='Over-the-shoulder shot', action='the Wizard unrolling a glowing treasure map across a desk for Uno and Aura, the map shows a dragon and a horned silhouette, books flapping around like birds',
     setting='round tower library with spiral bookshelves and floating candles', light='warm candlelight and violet crystal glow',
     refs=['wizard','uno','aura'], move='the map unrolls and a glowing path lights up across it', sec='books flap overhead, candle flames flicker', cam_m='locked off', exp=2.0)),
  (11, 'top-right', P(id='p05', loc="wizard's library", cam='close-up', moment='jester bonk',
     shot='Comedic close-up', action='the Jester juggling five glowing orbs, one orb bonking him on the head, his eyes spinning, the Wizard face-palming in the background',
     setting='library ladder and bookshelves', light='magenta and teal orb glow',
     refs=['jester','wizard'], move='the orbs arc up and one drops onto the jester\'s head', sec='hat bells jingle, dust motes', cam_m='locked off', exp=1.6,
     sfx=('BONK!', [0.72, 0.2], 8, [255, 120, 200]))),
 ]),
 ('page03', 15, 23, 'verse 1 - the road', [
  (15, 'top-left', P(id='p06', loc='dragon peaks', cam='extreme wide shot', moment='tiptoe past the sleeping dragon',
     shot='Extreme wide shot', action='Uno and Aura tiptoeing along a narrow cliff path past a giant sleeping chrome dragon curled on a mountain peak, puffing smoke rings while it snores',
     setting='jagged moonlit mountain peaks above the clouds', light='cool moonlight with purple glow from the dragon',
     refs=['uno','aura','dragon'], move='a smoke ring floats up from the snoring dragon while the heroes tiptoe', sec='clouds drift below, dragon belly rises and falls', cam_m='slow pan right', exp=2.2,
     sfx=('ZZZ...', [0.8, 0.2], -4, [200, 180, 255]))),
  (17, 'top-right', P(id='p07', loc='enchanted forest', cam='heroic low angle', moment='blade raised',
     shot='Heroic low-angle shot', action='Uno raising a glowing enchanted sword on a mossy boulder while tiny chrome fireflies swirl around the blade, Aura lighting the path with a cyan lantern of magic',
     setting='enchanted forest of crystal trees and giant glowing mushrooms', light='teal bioluminescence and a shaft of moonlight',
     refs=['uno','aura'], move='Uno lifts the sword and a gleam runs down the blade', sec='fireflies swirl, mushroom glow pulses', cam_m='locked off', exp=1.8,
     sfx=('SHIING!', [0.76, 0.24], -8, [255, 214, 0]))),
  (21, 'splash', P(id='s08', loc='forest clearing', cam='dynamic three-quarter splash', moment='shield for the weak',
     shot='Full splash, dynamic three-quarter view', action='Uno holding up a big round shield that blocks a shower of purple thorns, sheltering a family of tiny chrome robot rabbits who peek out and give him a thumbs-up',
     setting='misty forest clearing with crystal flowers', light='purple thorn glow against warm shield highlights',
     refs=['uno'], move='thorns bounce off the shield in sparks, the little rabbits peek out', sec='mist curls, flower petals flutter', cam_m='slow push-in', exp=2.0,
     sfx=('KLANG!', [0.78, 0.22], 7, [255, 214, 0]))),
 ]),
 ('page04', 23, 31, "chorus 2 - the jester's carnival", [
  (23, 'top-left', P(id='p09', loc="jester's carnival", cam='bird\'s-eye view', moment='carnival dance',
     shot="Bird's-eye view", action='a ring of chrome robot townsfolk dancing around a striped carnival tent, Uno and Aura in the middle doing a spin, balloons rising',
     setting="the jester's carnival at dusk with striped tents, a carousel and strings of lights", light='warm string lights and magenta dusk sky',
     refs=['crowd','uno','aura'], move='the ring of dancers circles and Aura spins under Uno\'s arm', sec='balloons rise, lights twinkle', cam_m='slow rotate', exp=2.0)),
  (27, 'top-right', P(id='p10', loc="jester's carnival", cam='dutch angle', moment='unicycle juggling',
     shot='Dutch-angle medium shot', action='the Jester on a wobbly unicycle juggling three tiny chrome robot puppies who are loving it, a chrome robot wolf pup in the crowd chasing its own tail',
     setting='carnival midway with a strongman bell and popcorn cart', light='popping teal and gold carnival lights',
     refs=['jester','wolf','crowd'], move='the puppies arc through the air in the juggle while the wolf pup spins after its tail', sec='popcorn pops, bunting sways', cam_m='locked off', exp=2.0,
     sfx=('WHEEE!', [0.76, 0.2], 6, [90, 230, 255]))),
 ]),
 ('page05', 31, 40, 'verse 2 - the beasts', [
  (31, 'top-left', P(id='p11', loc='dark woods', cam='ground-level wide', moment='wolf pack standoff',
     shot='Ground-level wide shot', action='a pack of chrome robot wolves leaping out of the dark woods at Uno and Aura, except one wolf in front distracted, chasing its own tail in circles',
     setting='twisted dark woods with fog and glowing red eyes in the trees', light='cold blue fog and red eye glow',
     refs=['wolf','uno','aura'], move='the wolves leap forward, the front wolf spins after its tail', sec='fog rolls, leaves blow', cam_m='locked off', exp=2.0,
     sfx=('AWOOO!', [0.74, 0.2], -6, [200, 220, 255]))),
  (33, 'top-right', P(id='p12', loc='spider cave', cam='upward from the cave floor', moment='web trap',
     shot='Worm\'s-eye view from the cave floor', action='a giant chrome robot spider dangling from its web above Aura, who lights the cave with a cyan orb, the spider tangled in its own web looking embarrassed',
     setting='crystal spider cave with huge glittering webs', light='cyan orb light and purple crystal reflections',
     refs=['spider','aura'], move='the spider wriggles in its web as the cyan orb brightens', sec='web strands sway, crystals sparkle', cam_m='slow push-in', exp=1.8,
     sfx=('THWIP!', [0.8, 0.5], -7, [255, 255, 255]))),
  (37, 'splash', P(id='s13', loc='cave mouth at dawn', cam='silhouette splash', moment='dawn breaks',
     shot='Full splash, backlit silhouette', action='Uno and Aura bursting out of the cave mouth into a blazing sunrise, a stream of little chrome spiders scurrying away waving tiny white flags',
     setting='mountain cave mouth over a valley at sunrise', light='huge golden sunrise backlight with lens flare',
     refs=['uno','aura','spider'], move='the heroes step into the light and the spiders scurry off', sec='sun rays flicker, dust glitters', cam_m='slow push-in', exp=2.2)),
 ]),
 ('page06', 40, 47, 'chorus 3 - the bat tower', [
  (40, 'top-left', P(id='p14', loc='bat tower', cam='extreme low angle', moment='bat swarm',
     shot='Extreme low-angle shot', action='a crooked tall tower against a giant moon, a swirling swarm of chrome robot bats pouring out of the top, Uno and Aura small at the door',
     setting='crooked spooky-cute tower on a hill', light='giant pale moon with violet sky',
     refs=['bat','uno','aura'], move='the bat swarm swirls out of the tower top', sec='moon glow pulses, grass sways', cam_m='slow tilt up', exp=2.0)),
  (42, 'top-right', P(id='p15', loc='bat tower', cam='upside-down shot', moment='sleepy bats',
     shot='Upside-down medium shot', action='a row of chrome robot bats hanging upside down from a beam, all bobbing their heads to music in their headphone ears, one bat asleep and slowly slipping off',
     setting='inside the tower on a spiral staircase', light='warm lantern light and purple shadows',
     refs=['bat'], move='the bats bob their heads to the beat and the sleepy one slips', sec='lantern sways, dust drifts', cam_m='locked off', exp=1.8,
     sfx=('BOP BOP', [0.76, 0.8], 5, [255, 214, 0]))),
  (44, 'bottom', P(id='p16', loc='bat tower', cam='wide interior shot', moment='lanterns lit',
     shot='Wide interior shot', action='Aura sending a wave of cyan fire that lights every lantern on the spiral staircase at once, Uno cheering, the bats spinning in a happy loop',
     setting='tall hollow tower interior with a spiral staircase', light='cyan fire racing up the tower',
     refs=['aura','uno','bat'], move='the cyan flame races up the spiral lighting each lantern', sec='bats loop, sparks drift', cam_m='slow tilt up', exp=2.0, focus=[0.5, 0.45],
     sfx=('FWOOSH!', [0.8, 0.3], -6, [90, 230, 255]))),
 ]),
 ('page07', 47, 56, 'verse 3 - the plains of peril', [
  (47, 'top-left', P(id='p17', loc='plains of peril', cam='aerial view', moment='knights march',
     shot='Aerial view', action="a column of the Sorcerer's chrome robot knights marching across a cracked purple plain toward a dark castle, one knight at the back tripping on his own spear",
     setting='cracked purple plains under storm clouds, the dark castle on the horizon', light='storm light with purple lightning in the distance',
     refs=['knight'], move='the column marches forward and the last knight stumbles', sec='storm clouds roll, dust kicks up', cam_m='slow push forward', exp=2.0)),
  (49, 'top-right', P(id='p18', loc='plains of peril', cam='extreme close-up', moment='magic arrow',
     shot='Extreme close-up', action="Aura drawing a bow made of cyan light, a glowing cyan magic arrow beside her red eye, focused and calm",
     setting='windswept rocky ridge above the plains', light='cyan arrow glow on chrome',
     refs=['aura'], move='Aura draws the light-bow and the arrow flares', sec='crimson-streaked hair blows', cam_m='locked off', exp=1.6,
     sfx=('ZWING!', [0.78, 0.8], -6, [90, 230, 255]))),
  (53, 'splash', P(id='s19', loc='plains battlefield', cam='side-on panoramic splash', moment='knight dominoes',
     shot='Full splash, side-on panorama', action="the cyan arrow bouncing off the first knight's helmet and the whole row of chrome robot knights toppling over like dominoes, Uno laughing with his hands on his hips",
     setting='the plains of peril with the dark castle behind', light='cyan streak and purple storm light',
     refs=['knight','uno','aura'], move='the knights topple one after another like dominoes', sec='shields bounce, dust puffs', cam_m='slow pan left', exp=2.4,
     sfx=('CLANG-CLANG-CLANG!', [0.6, 0.55], -4, [255, 214, 0]))),
 ]),
 ('page08', 56, 63, "chorus 4 - the dragon's lair", [
  (56, 'top-left', P(id='p20', loc="dragon's lair", cam='wide shot from behind a gold pile', moment='dragon wakes',
     shot='Wide shot from behind a pile of gold', action='the big chrome robot dragon waking up in its treasure cave, one eye opening, Uno and Aura peeking over the gold coins',
     setting='volcanic treasure cave full of gold coins and crystal stalactites', light='orange lava glow and purple throat glow',
     refs=['dragon','uno','aura'], move='the dragon opens one eye and lifts its head', sec='coins slide, lava glows', cam_m='slow push-in', exp=2.0)),
  (58, 'top-right', P(id='p21', loc="dragon's lair", cam='frontal close-up', moment='spark sneeze',
     shot='Comedic frontal close-up', action='the dragon sneezing a burst of harmless sparkly sparks, the Jester in front with his hat singed and smoking, blinking',
     setting='inside the treasure cave', light='bright gold sneeze sparks',
     refs=['dragon','jester'], move='the dragon sneezes and sparks spray, the jester blinks', sec='smoke curls from the hat', cam_m='locked off', exp=1.6,
     sfx=('AH-CHOO!', [0.76, 0.22], 7, [255, 214, 0]))),
  (61, 'splash', P(id='s22', loc='stormy sky', cam='flying action splash', moment='dragon ride',
     shot='Full splash, flying action shot', action="Uno and Aura riding the friendly chrome dragon through the storm clouds toward the Sorcerer's horned castle, Aura's cyan magic trailing behind",
     setting='stormy night sky above the clouds', light='lightning flashes and cyan trail glow',
     refs=['dragon','uno','aura'], move='the dragon beats its wings and banks toward the castle', sec='clouds whip past, coat flutters', cam_m='tracking alongside', exp=2.2,
     sfx=('WHOOSH!', [0.78, 0.82], -6, [90, 230, 255]))),
 ]),
 ('page09', 63, 72, 'verse 4 - the boss', [
  (63, 'top-left', P(id='p23', loc='forgotten ruins', cam='framed through a broken arch', moment='entering the lair',
     shot='Shot framed through a broken arch', action="Uno and Aura stepping through crumbling overgrown ruins toward a glowing purple doorway carved with horns",
     setting="forgotten ruins at the edge of the Sorcerer's lair, vines and floating rocks", light='purple doorway glow and green moss light',
     refs=['uno','aura'], move='the heroes step through the arch toward the glow', sec='vines sway, floating rocks bob', cam_m='slow push-in', exp=2.0)),
  (65, 'top-right', P(id='p24', loc='boss throne room', cam='low angle on the throne', moment='the music is caged',
     shot='Low-angle shot', action='the Horned Sorcerer lounging on a spiky throne, holding a birdcage full of glowing music notes, grinning smugly',
     setting='grand throne room with purple banners and a cracked marble floor', light='red and purple uplight',
     refs=['sorcerer'], move='the sorcerer taps the cage and the notes flutter', sec='banners ripple, purple orb glows', cam_m='slow push-in', exp=1.8)),
  (67, 'bottom', P(id='p25', loc='boss throne room', cam='wide two-shot', moment='magic clash',
     shot='Wide two-shot', action="the Sorcerer's purple lightning crashing into Aura's cyan shield while Uno charges forward with his sword",
     setting='the throne room floor cracking with energy', light='purple versus cyan clash flare',
     refs=['sorcerer','aura','uno'], move='purple lightning hits the cyan shield and splashes off', sec='floor cracks spark, cape billows', cam_m='locked off', exp=2.0, focus=[0.5, 0.45],
     sfx=('KRA-KOOM!', [0.76, 0.55], -4, [255, 214, 0]))),
  (69, 'splash', P(id='s26', loc='boss throne room', cam='impact close-up splash', moment='music set free',
     shot='Full splash, impact close-up', action="Uno's sword breaking the cage open, hundreds of glowing music notes bursting out like birds, the Sorcerer tumbling backwards with his crown of horns knocked crooked",
     setting='the throne room filling with light', light='white-gold burst light',
     refs=['uno','sorcerer'], move='the cage bursts and the notes fly out', sec='the sorcerer tumbles, sparkles fall', cam_m='slow push-in', exp=2.0,
     sfx=('KRAK-BOOM!', [0.62, 0.8], -7, [255, 214, 0]))),
 ]),
 ('page10', 72, 78, 'chorus 5 - the ballroom party', [
  (72, 'top-left', P(id='p27', loc='dance-party ballroom', cam='wide high angle', moment='the party starts',
     shot='Wide high-angle shot', action='a packed ballroom of chrome robot dancers under a giant spinning crystal disco chandelier, the freed music notes swirling above them',
     setting='palace ballroom with laser beams and a mirror floor', light='purple and cyan lasers',
     refs=['crowd'], move='the chandelier spins and the crowd jumps on the beat', sec='lasers sweep, notes swirl', cam_m='slow rotate', exp=2.0)),
  (74, 'top-right', P(id='p28', loc='dance-party ballroom', cam='medium two-shot', moment='the reformed sorcerer dances',
     shot='Medium two-shot', action='the reformed Horned Sorcerer doing an awkward robot dance with the Jester, a wolf and a bat dancing beside them',
     setting='edge of the ballroom dance floor', light='magenta spotlight',
     refs=['sorcerer','jester','wolf','bat'], move='the sorcerer does a stiff robot dance and the jester copies him', sec='wolf wags, bat flaps', cam_m='locked off', exp=2.0,
     sfx=('BOING!', [0.76, 0.2], 6, [255, 120, 200]))),
  (76, 'bottom', P(id='p29', loc='dance-party ballroom', cam='spotlight centre-stage', moment='dance-off',
     shot='Centre-stage spotlight shot', action='Uno and Aura in a dance-off in a circle of light, Uno spinning on his back, Aura striking a pose with cyan sparkles, the crowd cheering',
     setting='centre of the ballroom dance floor', light='single white spotlight and cyan sparkles',
     refs=['uno','aura','crowd'], move='Uno spins on his back and Aura hits a pose', sec='crowd claps, sparkles fall', cam_m='slow push-in', exp=2.2, focus=[0.5, 0.42],
     sfx=('WOOO!', [0.8, 0.25], -6, [90, 230, 255]))),
 ]),
 ('page11', 78, None, 'outro - victory', [
  (78, 'top-left', P(id='p30', loc='palace hallway', cam='tracking side view', moment='conga line',
     shot='Tracking side view', action='a conga line of the Knights, the wolves, the spiders and the Jester snaking down a palace hallway, the spider using all eight legs to keep the beat',
     setting='long palace hallway with tall windows and banners', light='warm morning light through windows',
     refs=['knight','wolf','spider','jester'], move='the conga line bounces along step by step', sec='banners sway, light beams shimmer', cam_m='slow pan', exp=2.0)),
  (81, 'top-right', P(id='p31', loc='palace balcony DJ booth', cam='over-the-decks shot', moment='wizard DJ',
     shot='Over-the-decks shot', action='the Wizard DJing on glowing chrome turntables with the dragon beside him blowing smoke rings in the shape of hearts',
     setting='palace balcony DJ booth above the party', light='violet and pink stage light',
     refs=['wizard','dragon'], move='the wizard scratches a record and the dragon blows a heart-shaped smoke ring', sec='beard sways, lights pulse', cam_m='locked off', exp=1.8,
     sfx=('WIKKA-WIKKA!', [0.74, 0.8], -5, [255, 214, 0]))),
  (85, 'splash', P(id='s32', loc='castle rampart at sunrise', cam='epic wide victory splash', moment='sunrise victory',
     shot='Full splash, epic wide shot', action='Uno and Aura standing on the castle rampart at sunrise, waving, with the whole cast and townsfolk cheering behind them, the dragon curled around a tower and bats circling',
     setting='the chrome kingdom restored, rainbow over the hills', light='golden sunrise and a soft rainbow',
     refs=['uno','aura','wizard','jester','knight','sorcerer','dragon','bat','crowd'], move='everyone waves and the sun rises', sec='banners ripple, bats circle', cam_m='slow pull-back', exp=2.4)),
 ]),
]
NARR = {'p30': 'AND THE MUSIC CAME HOME.', 's32': 'KINGDOM COME.'}

def build():
    pages, prompts, rows = [], [], []
    for pid, sdb, edb, note, items in PAGES:
        start = DB[sdb] if sdb else 0.0
        end = DB[edb] if edb is not None else END
        lands = [DB[db] for db, _, _ in items]
        pg = {'id': pid, 'note': note, 'start': round(start, 3), 'end': round(end, 3), 'panels': []}
        for k, (db, slot, f) in enumerate(items):
            land = DB[db] if db else B[0]
            nxt = lands[k + 1] if k + 1 < len(items) else end
            chars = '; '.join(CAST[r] for r in f['refs'])
            prompt = STYLE.format(shot=f['shot'], action=f['action'], setting=f['setting'], light=f['light'], chars=chars)
            motion = MOTION.format(move=f['move'].capitalize(), sec=f['sec'], cam=f['cam_m'])
            lyr = [(t, s) for t, s in LYR if land - 0.6 <= t < nxt - 0.3] if not (k == 0 and pid == 'page01') else [(t, s) for t, s in LYR if t < nxt - 0.3]
            caps = []
            anchors = ['tl', 'bl'] if slot != 'splash' else ['tl', 'bl']
            if f['id'] in NARR:
                caps.append({'text': NARR[f['id']], 'anchor': 'tl', 'at': round(next_beat(land) if land > B[0] else B[0], 3)})
            for i, (t, s) in enumerate(lyr[:2]):
                at = max(snap(t), land)
                caps.append({'text': s, 'anchor': anchors[i], 'at': round(at, 3), 'lyric': True, **({'estimated': True} if t in EST else {})})
            u = {'id': f['id'], 'image': f'panels/{f["id"]}.jpg', 'at': round(land, 3),
                 'location': f['loc'], 'camera': f['cam'], 'moment': f['moment'],
                 'scene': f"{f['shot']} of {f['action']}, {f['setting']}",
                 'prompt': prompt, 'refs': f['refs'], 'motionPrompt': motion,
                 'clip': {'src': f'clips/{f["id"]}.mp4', 'in': None, 'out': None, 'expected': f['exp']},
                 'lyric': ' / '.join(s for _, s in lyr[:2]), 'captions': caps}
            if 'focus' in f: u['focus'] = f['focus']
            if 'sfx' in f:
                txt, pos, rot, col = f['sfx']
                u['sfx'] = [{'text': txt, 'at': round(next_beat(next_beat(land)), 3), 'pos': pos, 'rot': rot, 'size': 0.17 if slot != 'splash' else 0.2, 'color': col}]
            if slot == 'splash':
                prev = pg['panels'][-1]
                dur = land - max(b for b in B if b < land - 0.05)
                pg['transition'] = {'type': 'zoom', 'panel': prev['id'], 'at': round(land, 3), 'dur': round(dur, 3)}
                pg['splash'] = u
            else:
                u['slot'] = slot
                pg['panels'].append(u)
            prompts.append({'id': f['id'], 'prompt': prompt, 'refs': f['refs']})
            rows.append((pid, slot, u, f, round(dur, 3) if slot == 'splash' else None))
        pages.append(pg)
    spec = {'title': 'Kingdom Come - comic mode, full song (DRAFT plan; art not generated yet)', 'draft': True,
            'assetsDir': '/workspace/kingdom-come-comic', 'fps': 30, 'defaults': {'holdBeats': 1},
            'song': {'suno': '7bf4887f-eec0-4614-a285-5557aa4382d5',
                     'audio': 'channels/progressiveslop/songs/7bf4887f-eec0-4614-a285-5557aa4382d5/song.m4a',
                     'audioNote': 'not committed; copy from the channel folder (same file as shots/kingdom-come-v4/stage/assets/song.m4a)',
                     'timeline': 'shots/kingdom-come-16bit/stage/timeline.json', 'start': 0.0, 'end': END, 'loudness': -14},
            'cast': CAST, 'styleTemplate': STYLE, 'motionTemplate': MOTION, 'pages': pages}
    return spec, prompts, rows

if __name__ == '__main__':
    spec, prompts, rows = build()
    os.makedirs(f'{REPO}/shots/kingdom-come-comic', exist_ok=True)
    json.dump(spec, open(f'{REPO}/shots/kingdom-come-comic/kingdom-come-comic.comic.json', 'w'), indent=1, ensure_ascii=False)
    json.dump(prompts, open('/workspace/kingdom-come-comic/prompts.json', 'w'), indent=1, ensure_ascii=False)
    import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import plan_md; plan_md.write(spec, rows, B)
    print(len(prompts), 'panels')
