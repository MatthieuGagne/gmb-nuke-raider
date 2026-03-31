-- tools/create_overmap_car.lua
-- Creates assets/sprites/overmap_car.aseprite with 2 frames:
--   Frame 1: up-facing arrow (vertical tile, used for up/down via flip)
--   Frame 2: left-facing arrow (horizontal tile, used for left/right via flip)
-- Run with: aseprite --batch --script tools/create_overmap_car.lua
-- (run from the worktree root so relative paths resolve)

-- Pixel data: 0=white(transparent), 3=black(solid)
-- 8x8 up arrow (↑)
local up = {
  0,0,0,3,3,0,0,0,
  0,0,3,3,3,3,0,0,
  0,3,3,3,3,3,3,0,
  3,3,0,3,3,0,3,3,
  0,0,0,3,3,0,0,0,
  0,0,0,3,3,0,0,0,
  0,0,0,3,3,0,0,0,
  0,0,0,3,3,0,0,0,
}

-- 8x8 left arrow (←)
local left = {
  0,0,0,3,0,0,0,0,
  0,0,3,3,0,0,0,0,
  0,3,3,3,3,3,3,3,
  3,3,3,3,3,3,3,3,
  0,3,3,3,3,3,3,3,
  0,0,3,3,0,0,0,0,
  0,0,0,3,0,0,0,0,
  0,0,0,0,0,0,0,0,
}

-- Create 8x8 indexed sprite (1 frame, 1 layer to start)
local spr = Sprite(8, 8, ColorMode.INDEXED)

-- Match existing sprite palette:
--   index 0 = white (255,255,255) — transparent
--   index 1 = light gray (85,85,85)
--   index 2 = medium gray (170,170,170)
--   index 3 = black (0,0,0)
local pal = Palette(4)
pal:setColor(0, Color{r=255, g=255, b=255, a=255})
pal:setColor(1, Color{r=85,  g=85,  b=85,  a=255})
pal:setColor(2, Color{r=170, g=170, b=170, a=255})
pal:setColor(3, Color{r=0,   g=0,   b=0,   a=255})
spr:setPalette(pal)

local layer = spr.layers[1]

-- Frame 1: up arrow (sprite starts with 1 frame + 1 blank cel)
local img1 = Image(8, 8, ColorMode.INDEXED)
for y = 0, 7 do
  for x = 0, 7 do
    img1:drawPixel(x, y, up[y * 8 + x + 1])
  end
end
spr:newCel(layer, spr.frames[1], img1, Point(0, 0))

-- Frame 2: left arrow
local frame2 = spr:newFrame()
local img2 = Image(8, 8, ColorMode.INDEXED)
for y = 0, 7 do
  for x = 0, 7 do
    img2:drawPixel(x, y, left[y * 8 + x + 1])
  end
end
spr:newCel(layer, frame2, img2, Point(0, 0))

spr:saveAs("assets/sprites/overmap_car.aseprite")
print("Created assets/sprites/overmap_car.aseprite (2 frames: up + left)")
