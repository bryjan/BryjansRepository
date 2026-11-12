# Mech size-class reference

This document is a design guide for balancing new mech classes. It is not a
set of enforced rules: terrain, weapons, modules, and intended role can justify
an exception. Use the ranges to make the tradeoff clear and deliberate.

## Reading the values

- **Armor / HP** are suggested values for each major part: hull, helm, legs,
  or a weapon limb.
- **AP** is the helm's action-point contribution.
- **Mobility** is the legs' movement-point contribution before terrain costs.
- **Energy** is written as `capacity / generation each round`.
- **Visual / radar** are the helm's basic sensor values. Radar signature comes
  from the hull and is easier for opposing sensors to detect when higher.

The current **Lancer** is the size 2 baseline: a fast power-armored skirmisher
with size 2, armor 5, roughly 25–30 HP per main part, AP 6, mobility 4, energy
20 / 1, visual range 12, and no active radar.

## Typical values by size

| Size | Label | Typical role | Armor / HP per major part | AP | Mobility | Energy | Visual / radar | Radar signature |
|---:|---|---|---|---:|---:|---|---|---|
| 0 | Flat | Emplacement, mine, drone, wreck | 0–3 / 1–12 | 0–2 | 0 | 0–8 / 0–1 | 0–6 / 0–8 | 0–40 |
| 1 | Tiny | Light exosuit, scout, combat drone | 2–4 / 12–22 | 3–5 | 4–6 | 8–18 / 1–3 | 6–14 / 0–15 | 40–150 |
| 2 | Small | Lancer, line skirmisher | 4–7 / 22–35 | 5–7 | 3–5 | 16–30 / 1–3 | 10–18 / 0–25 | 150–300 |
| 3 | Medium | Hunter, sensor mech, main battle unit | 6–10 / 35–55 | 6–8 | 2–4 | 30–70 / 2–5 | 14–28 / 15–55 | 300–600 |
| 4 | Large | Breakthrough, fire-support, command mech | 9–14 / 55–85 | 7–9 | 1–3 | 55–110 / 3–7 | 18–35 / 20–75 | 550–900 |
| 5 | Huge | Siege platform, heavy command unit | 13–19 / 85–130 | 8–10 | 1–2 | 90–170 / 4–10 | 22–45 / 25–100 | 850–1,400 |
| 6 | Titanic | Strategic asset, fortress walker | 18–28 / 130–220 | 9–12 | 0–1 | 150–280 / 6–14 | 30–60 / 35–140 | 1,300–2,200 |

## Balance rules of thumb

1. Each size step should normally add roughly **35–60% more total durability**.
   Armor, HP, or both can supply that increase.
2. Larger does not always mean faster. A mech that keeps the previous size's
   mobility spends part of its balance budget on actuators, energy, or reduced
   armor elsewhere.
3. A mech should have one clear advantage and one counterplay path. High armor
   can mean poor sensors; long range can mean low burst damage; strong radar can
   mean a high signature.
4. Judge weapons by total action output, not only damage per projectile. A
   multi-projectile weapon, low AP cost, or high accuracy can make a modest
   damage value very dangerous.
5. Capacity and generation are different tools. Capacity decides how hard a
   mech can surge; generation decides how long it can maintain pressure.

## Size 3 sensor-skirmisher target: Kestrel Type.A

The proposed Kestrel sits at size 3 and intentionally breaks the usual medium
energy profile.

| Area | Suggested target | Reason |
|---|---|---|
| Armor / HP | 7–9 armor, 40–50 HP per main part | Survives a fight with multiple Lancers without becoming a pure brawler. |
| AP / mobility | AP 7, mobility 4 | Keeps Lancer-like movement while gaining a larger sensor and equipment budget. |
| Energy | 65–80 capacity, **1–2 generation** | Enables a powerful opening burst but creates a long recovery window. |
| Sensors | Visual 20–24, radar 35–50, passive radar | Lets it identify and shape engagements before close combat begins. |
| Signature | 450–600 | Active scanning exposes it to other sensor-equipped units. |
| Main gun | Longwatch Beam Carbine: low damage, high accuracy, above-average range, 6–10 energy per shot | Applies steady pressure at range while forcing hard energy decisions. |

### Kestrel play pattern

1. **Opening:** Scan, identify, and claim a firing lane using stored energy.
2. **Burst:** Move aggressively or fire several accurate long-range shots.
3. **Recovery:** Reduce activity, reposition behind terrain, and avoid a close
   fight while energy generation catches up.

This lets one Kestrel outplay two or three Lancers through information and
timing. It loses that advantage if it wastes energy early or is forced into a
long, close-range engagement.
