# Sculptural brief — ConRol award figure

A commission brief for the figure at the top of the ConRol 2026 award. Written
to be usable three ways: as a prompt for an image-to-3D generator, as a brief for
a human modeller, and as the specification that `scripts/fist_elegant.py`
implements. Read it as a sculptural problem, not a decorative one.

---

## 1. Subject

A single human hand, right hand, closed into a **relaxed fist gripping an implied
cylindrical handle**, with the **little finger (pinky) extended upward** in the
gesture of someone lifting a teacup with affected refinement.

The emotion is the whole point. This is not a fighter's fist. It is the hand of a
person being **deliberately, comically precious** — the *snob* gesture. Every
decision below serves one of two masters: the anatomy that makes the hand
credible, and the pose that makes the joke land.

## 2. The pose, joint by joint

State the articulation explicitly, because it is what separates a hand from a
lump.

- **Metacarpophalangeal joints (the knuckles), fingers 2–4** (index, middle,
  ring): flexed approximately 85–90°. These three fingers are **curled into the
  palm** as if closed around a handle roughly 30 mm in diameter. They are not
  clenched white-knuckled; the curl is loose and composed.
- **Proximal interphalangeal joints (the second knuckle row), fingers 2–4**:
  flexed approximately 100–110°. This is the row that must be visible as a
  **second tier of articulation** below the knuckles. A fist with only one row of
  bumps reads as a box; two rows read as a hand.
- **Distal phalanges, fingers 2–4**: tucked into the palm, largely hidden. Do not
  attempt to model them as separate features — they are occluded, and pretending
  otherwise creates visual noise.
- **Thumb**: the metacarpal lies along the radial side; the **proximal phalanx
  crosses the front of the curled index and middle fingers**, and the **distal
  phalanx angles down across them** at roughly 20–30° from the proximal segment.
  The thumb must visibly **overlap and occlude** the lower part of the finger
  grooves.
- **The pinky — the hero.** Three phalanges, extended and **gently flexed at every
  joint**, never a straight rod:
  - MCP: extended but with a **slight forward flexion**, around 7–9°
  - PIP: a **slight counter-flexion**, around 4–6°, which is what gives the finger
    its relaxed elegance instead of a rigid salute
  - DIP: a further slight counter-flexion, around 5–7°, letting the tip settle
  - The result is a **shallow S-curve**, the way a real extended little finger
    behaves. It must be perceptible. A straight pinky looks like a poker, not a
    gesture.
- **Wrist**: neutral, tapering, no flexion. The award stands on it.

## 3. Landmarks that must survive stylisation

At 60 % abstraction these are the last things to sacrifice, in priority order:

1. **Three knuckles in a row, and the pinky column bare.** The raised finger must
   read as the *fourth* finger along, with the thumb on the opposite side fixing
   the handedness. This is non-negotiable: without it the viewer sees "a finger",
   not "the little finger".
2. **The pinky is the narrowest and shortest-necked digit**, and the only one
   articulated into visible segments above the fist.
3. **The second articulation row** (PIP) below the knuckles, on the three curled
   fingers.
4. **The knuckle line descends from the radial to the ulnar side** — the index
   knuckle is the highest, the pinky knuckle the lowest. This is anatomy, and it
   also implies the pinky has further to travel to stand proud.
5. **Thenar eminence**: the thumb-side pad, a faceted swelling at the base of the
   thumb.
6. **Hypothenar eminence**: the pinky-side pad. Easy to forget and worth
   including — it is what tells the eye which side of the hand it is looking at.

## 4. Style: 60 % geometric abstraction, 40 % anatomical observation

Read the ratio as a budget, not a mood.

- **70–60 %**: the form is built from **flat planes and clean faceted planes**.
  Chosen, deliberate facets. No organic blobbing, no subdivision-surface
  smoothing, no "sculpted clay" softness anywhere.
- **30–40 %**: the underlying volumes follow real anatomy. The hand *swells* from
  the narrow wrist to the broad knuckle line and then tapers. The fingers converge
  slightly toward the wrist. Nothing is a constant-width extrusion.

Concretely:

- The silhouette must **taper**. A hand is widest across the knuckles and narrows
  at the wrist; a figure built as a uniform block is dead on arrival.
- Facets should **read as planes catching light**, roughly 4–7 mm wide. Bigger and
  it is a cut gemstone; smaller and the facets vanish at arm's length.
- **Sharp creases, no fillets** except where a crease would be structurally
  fragile.
- The mood to aim for is a **carved form**, closer to Brancusi or a polished
  mineral specimen than to a 3D-printed toy. Refined, a little cold, quietly
  funny.
- Elegance comes from **proportion and restraint**, not from ornament. When in
  doubt, remove a feature rather than add one.

## 5. Hard constraints

- **Height**: 74 mm of figure visible above the socket, 100 mm for the assembled
  award.
- **Footprint**: the body must not exceed roughly 40 × 28 mm.
- **Mount**: a rectangular tenon **30 × 22 × 5.7 mm** at the base, centred,
  dropping into a 30.5 × 22.5 × 6 mm mortise. 0.25 mm of clearance per side.
- **Printability on FDM, no supports**:
  - no overhang steeper than 45° from vertical
  - no self-supporting bridges wider than ~2 mm
  - minimum wall and minimum feature **1.6 mm**
  - the pinky must be at least **7 mm** across at its thinnest
  - every added articulation block must be a **truncated pyramid**, so its own
    surfaces self-support or bridge in under 2 mm
- **Watertight, single shell**, positive volume, no internal voids.
- **Orientation**: model it upright as described. The printer will lay it down.

## 6. What to avoid

- A pinky that is a straight cylinder, or that reads as a pointing index finger.
- Only one row of knuckles.
- Any smooth, organic, "melted" surface — the abstraction is the style.
- Uniform-width or uniform-depth extrusions.
- Ornament that is not anatomy: no rings, no cuffs, no fabric, no nail detail.
- Delivering a flat silhouette. This is a three-dimensional object; the pose has
  to read from a three-quarter view, not only head-on.

## 7. Deliverable

A single watertight mesh, 60 % faceted and 40 % observed, of a right hand in the
snob teacup pose, little finger raised with a perceptible gentle flexion at every
joint, mounted on the specified tenon, printable without supports on a 0.4 mm
nozzle.
