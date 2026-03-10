# Wasteland Driver
Game Design Document (Draft v0.2)

---

# 1. Game Overview

Genre: Top-down racing / mission-based driving / light RPG  
Platform: Nintendo Game Boy (DMG, possibly GBC enhanced)

Core Fantasy:
You are a wasteland courier and driver competing in dangerous races across a ruined world to earn money, upgrade your car, and uncover the story behind the wasteland.

Gameplay Pillars

1. Skill-based racing — tight tracks and aggressive AI
2. Vehicle progression — meaningful upgrades
3. Mission variety — races, deliveries, chases, survival
4. Hub exploration — NPC interaction and upgrades

---

# 2. Core Gameplay Loop

Visit Hub  
→ Talk to NPCs / accept mission  
→ Start race or driving mission  
→ Complete mission  
→ Earn money + reputation  
→ Upgrade car  
→ Unlock new missions or regions  

Optional:
Random road encounters while traveling.

---

# 3. Gameplay Loops

Main gameplay is divided into four loops:

- Racing Loop
- Hub Loop
- Overmap Loop
- Dialogue Loop

---

## Racing Loop

Race Start  
→ Drive through track  
→ Avoid hazards and opponents  
→ Complete objectives  
→ Finish race  
→ Receive rewards

Objectives may include:

- Win race
- Deliver cargo
- Escape pursuers
- Survive attacks

Rewards:

- Scrap (currency)
- Reputation
- Mission unlocks

---

## Hub Loop

Enter Hub  
→ Talk to NPCs  
→ Accept missions  
→ Upgrade vehicle  
→ Buy items  
→ Leave hub

Hub features:

- Garage
- Mission givers
- Traders
- Save location

---

## Overmap Loop

Leave hub  
→ Travel across wasteland  
→ Possible encounter  
→ Reach destination

Encounters:

- Ambush
- Random race
- Delivery request
- Story event

---

## Dialogue Loop

Approach NPC  
→ Dialogue appears  
→ Player advances text  
→ Optional choice  
→ Dialogue ends

Example:

DRIFTER:
"Road east ain't safe.  
But the pay's good."

---

# 4. Player Controls

D-Pad: Steering  
A: Accelerate  
B: Brake / Reverse  
Select: Fire weapon  
Start: Pause  

Optional: A+B = Boost

---

# 5. Camera & Perspective

Top-down perspective.

Characteristics:

- Player car centered
- Scrolling tile map
- Clear track edges

---

# 6. Game World

Example regions:

Rust Town — scrap settlement  
Salt Flats — open desert  
Dead Highway — ruined highway  
Toxic Zone — industrial ruins

Each region includes:

- Hub
- 3–5 missions
- Boss race

---

# 7. Hubs

Small explorable areas.

Locations:

Garage — upgrades  
Bar — missions  
Market — items  
Mechanic — story hints

Movement usually on foot.

---

# 8. Missions

Race — standard race  
Delivery — transport cargo  
Elimination — last place removed  
Chase — catch or escape  
Survival — survive enemy attacks

---

# 9. Vehicles

Stats:

Speed — maximum velocity  
Acceleration — speed buildup  
Handling — turning responsiveness  
Armor — durability  
Fuel — endurance

---

# 10. Vehicle Weapons

Possible weapons:

Machine Gun — rapid fire  
Rocket — high damage projectile  
Mines — dropped behind vehicle  
Oil Slick — slippery hazard

Pickups:

Ammo crate  
Weapon crate  
Repair kit

---

# 11. Upgrades

Engine — higher speed  
Tires — better grip  
Suspension — off-road control  
Armor plates — more health  
Turbo — temporary boost

---

# 12. Economy

Currency: Scrap

Sources:

- Race rewards
- Missions
- Pickups
- Selling parts

---

# 13. Damage System

Vehicles have HP.

Damage from:

- Collisions
- Hazards
- Enemy weapons

Effects:

- Smoke
- Reduced performance

---

# 14. NPC System

Mechanic — upgrades  
Racer — rivals  
Trader — items  
Drifter — lore

---

# 15. Story

The wasteland was once connected by highways.

Drivers now connect isolated settlements.

Factions:

Road Guild — drivers and couriers  
Scrap Kings — bandits  
Old World Corp — lost technology group

---

# 16. Enemy Drivers

Aggressive — ramming  
Fast — high speed  
Tank — heavy armor  
Sneaky — evasive

Boss drivers have unique vehicles.

---

# 17. Minimum Viable Game

1 hub  
1 player car  
3 tracks  
basic upgrades  
3 AI opponents

Goal: playable gameplay loop.

---

# 18. Stretch Goals

More regions  
Boss races  
Weather effects  
Random encounters  
Car skins

---

# 19. Game State Machine

Boot  
→ Main Menu  
→ Hub  
→ Mission Select  
→ Race/Mission  
→ Results  
→ Return to Hub

---

# 20. Track Tile System

Road — normal  
Sand — slow terrain  
Scrap — obstacles  
Oil — slippery  
Boost — speed tile

Maps use tile layers:

- terrain
- collision
- decoration

---

# 21. Car Physics Model

Simplified physics:

velocity += acceleration  
velocity -= friction  
position += velocity

Turning slightly reduces speed.

Terrain modifies grip and friction.

---

# 22. Mission Scripting System

Example mission format:

MISSION_ID: 03  
TYPE: RACE  
TRACK: SALT_FLATS_1  
LAPS: 3  
OPPONENTS: 4  
REWARD: 150

Delivery mission:

MISSION_ID: 07  
TYPE: DELIVERY  
START: RUST_TOWN  
END: DEAD_HIGHWAY  
TIME_LIMIT: 90  
REWARD: 200

---

# 23. Dialogue Data Structure

NPC_ID: MECHANIC_01  
LINE_1: "Your engine sounds rough."  
LINE_2: "I can fix it for the right price."  

CHOICE:  
1 Upgrade car  
2 Leave

---

# 24. Memory Budget (Game Boy)

ROM: ~256KB–1MB  
Sprites: 40 total  
Max per scanline: 10

Optimization:

- reuse tiles
- short dialogue
- small maps

---

# 25. Development Roadmap

Phase 1 — Prototype  
- car physics  
- scrolling track  

Phase 2 — Core Gameplay  
- race mode  
- upgrades  
- hub system  

Phase 3 — Content  
- missions  
- regions  
- story  

Phase 4 — Polish  
- balancing  
- bug fixing  
- sound