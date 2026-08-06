# sprites/body — Body

z-order: 6 | required: True | dimensions: 2048x2048 RGBA PNG (illustration profile)

> **DERIVED ART** — produced by `engine/artgen/body.py` from the vaulted source
> plates, regenerate with `python scripts/gen_art.py --layer body`. Sources are
> read from [`vault/sprites-v1/body/`](../../vault/README.md), never from this
> directory, so the derivation is idempotent.

## The defect this fixed

These 48 filenames used to resolve to only **12 unique images**. `blue`,
`emerald`, `green` and `zombie` were byte-identical to one another, and
`chrome`, `corrupted`, `ghost` and `gold` each repeated a single image across
all six poses — so "Blue Standing" and "Green Sitting" minted the *same
picture*. That is a fairness problem as much as an art one: a buyer paying for
a rarer combination received a duplicate.

A second, quieter defect: the trait names did not describe the art.
`blue_on_bow` rendered a **red** character.

## The drawn pupil is removed

Each source plate has its **pupil** deleted before the colourway is applied, so
the `eyes` trait can draw its own. Without this every NFT that rolls an eye
trait shows two pupils.

Only the pupil goes. The iris, sclera, eyelid and socket — the hand-drawn
linework that makes these plates good — all survive and go on framing the eye.
Removing more was tried and rejected: masking the whole eye and inpainting
(Telea and Navier-Stokes, several radii) smears, because the eye sits inside a
network of contour lines and diffusion cannot invent line art.

The fill takes colour from the iris ring immediately around the pupil, by
nearest surviving donor, then blurs — so it inherits that eye's own local
shading rather than a flat average. Alpha is never touched, so the silhouette
and compositing behaviour cannot change.

Only the *dominant* eye is blanked. Two-eyed characters keep their far eye
exactly as drawn, which matches the one-pupil design of the `eyes` layer.

## How it works now

The filename means what it says: **pose selects the composition, variant
selects the colourway.**

Each plate is its pose's drawing pushed through that variant's *gradient map* —
a luminance-indexed remap onto a master-palette ramp. Line weight, shading and
every tonal relationship survive exactly (alpha is passed through untouched);
only the palette changes. All 48 outputs now differ.

All twelve original illustrations stay in service: the five shared pose plates
supply five poses, and each variant that had bespoke standing art keeps it as
*its* standing source.

| variant | bucket | colourway |
|---|---|---|
| green | common | natural muted green |
| blue | uncommon | pale blue → ink |
| zombie | rare | sickly; midtones grey before shadows go violet |
| ghost | epic | spectral, but the shadow end still reaches a true dark — a ramp that stops at grey vanishes into the bone-white ground |
| corrupted | epic | lavender → violet → ink |
| gold | legendary | treasure light |
| emerald | legendary | Chia-coded jewel contrast |
| chrome | mythic | achromatic |

Body plates are larger than the generated layers (~2.6 MB mean) and that is
inherent: RGB accounts for ~3 MB of a 3.5 MB plate despite only ~240 distinct
colours, because the source illustration's texture varies pixel to pixel and
defeats PNG's predictors.

| file | trait |
|---|---|
| `green_standing.png` | Green x Standing |
| `green_saluting.png` | Green x Saluting |
| `green_sitting.png` | Green x Sitting |
| `green_on_bow.png` | Green x On Bow |
| `green_back_turned.png` | Green x Back Turned |
| `green_looking_down.png` | Green x Looking Down |
| `blue_standing.png` | Blue x Standing |
| `blue_saluting.png` | Blue x Saluting |
| `blue_sitting.png` | Blue x Sitting |
| `blue_on_bow.png` | Blue x On Bow |
| `blue_back_turned.png` | Blue x Back Turned |
| `blue_looking_down.png` | Blue x Looking Down |
| `zombie_standing.png` | Zombie x Standing |
| `zombie_saluting.png` | Zombie x Saluting |
| `zombie_sitting.png` | Zombie x Sitting |
| `zombie_on_bow.png` | Zombie x On Bow |
| `zombie_back_turned.png` | Zombie x Back Turned |
| `zombie_looking_down.png` | Zombie x Looking Down |
| `ghost_standing.png` | Ghost x Standing |
| `ghost_saluting.png` | Ghost x Saluting |
| `ghost_sitting.png` | Ghost x Sitting |
| `ghost_on_bow.png` | Ghost x On Bow |
| `ghost_back_turned.png` | Ghost x Back Turned |
| `ghost_looking_down.png` | Ghost x Looking Down |
| `corrupted_standing.png` | Corrupted x Standing |
| `corrupted_saluting.png` | Corrupted x Saluting |
| `corrupted_sitting.png` | Corrupted x Sitting |
| `corrupted_on_bow.png` | Corrupted x On Bow |
| `corrupted_back_turned.png` | Corrupted x Back Turned |
| `corrupted_looking_down.png` | Corrupted x Looking Down |
| `gold_standing.png` | Gold x Standing |
| `gold_saluting.png` | Gold x Saluting |
| `gold_sitting.png` | Gold x Sitting |
| `gold_on_bow.png` | Gold x On Bow |
| `gold_back_turned.png` | Gold x Back Turned |
| `gold_looking_down.png` | Gold x Looking Down |
| `emerald_standing.png` | Emerald x Standing |
| `emerald_saluting.png` | Emerald x Saluting |
| `emerald_sitting.png` | Emerald x Sitting |
| `emerald_on_bow.png` | Emerald x On Bow |
| `emerald_back_turned.png` | Emerald x Back Turned |
| `emerald_looking_down.png` | Emerald x Looking Down |
| `chrome_standing.png` | Chrome x Standing |
| `chrome_saluting.png` | Chrome x Saluting |
| `chrome_sitting.png` | Chrome x Sitting |
| `chrome_on_bow.png` | Chrome x On Bow |
| `chrome_back_turned.png` | Chrome x Back Turned |
| `chrome_looking_down.png` | Chrome x Looking Down |
