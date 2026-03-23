GBDK_HOME ?= /opt/gbdk
LCC       := $(GBDK_HOME)/bin/lcc

CFLAGS    := -Wa-l -Wl-m -Wl-j -Wm-ya32 -autobank -Wb-ext=.rel -Ilib/hUGEDriver/include
ifeq ($(DEBUG),1)
CFLAGS += -DDEBUG
endif
ROMFLAGS  := -Wm-yc -Wm-yt25 -Wm-yn"NUKE RAIDER"

TARGET    := build/nuke-raider.gb
OBJ_DIR   := build/obj

SRCS      := $(wildcard src/*.c)
OBJS      := $(patsubst src/%.c,$(OBJ_DIR)/%.o,$(SRCS))

UNITY_SRC    := tests/unity/src/unity.c
TEST_SRCS    := $(wildcard tests/test_*.c)
TEST_FLAGS   := -Itests/mocks -Itests/unity/src -Isrc -Ilib/hUGEDriver/include -Wall -Wextra
TEST_LIB_SRC := $(filter-out src/main.c,$(wildcard src/*.c))
MOCK_SRCS    := $(wildcard tests/mocks/*.c)

.PHONY: all clean test test-tools export-sprites bank-check bank-post-build memory-check dialog_data

all: $(TARGET)

# ── Generated sources ─────────────────────────────────────────────────────────
# src/track_map.c is checked into git so CI works without Python/Tiled.
# Running `make src/track_map.c` (or plain `make`) regenerates it when needed.
src/track_map.c: assets/maps/track.tmx tools/tmx_to_c.py
	python3 tools/tmx_to_c.py assets/maps/track.tmx src/track_map.c

# Ensure regeneration happens before ROM link if TMX is newer
$(TARGET): src/track_map.c

# ── Aseprite → PNG export (requires aseprite in PATH) ─────────────────────────
# .aseprite files are the canonical source. PNGs are checked in so CI works
# without Aseprite installed. Run `make export-sprites` to re-export from source.
assets/maps/tileset.png: assets/maps/tileset.aseprite
	aseprite --batch $< --save-as $@

assets/sprites/%.png: assets/sprites/%.aseprite
	aseprite --batch $< --save-as $@

export-sprites: assets/maps/tileset.png $(patsubst assets/sprites/%.aseprite,assets/sprites/%.png,$(wildcard assets/sprites/*.aseprite))

# src/track_tiles.c is checked into git so CI works without Python.
# Running `make src/track_tiles.c` (or plain `make`) regenerates it when needed.
src/track_tiles.c: assets/maps/tileset.png tools/png_to_tiles.py
	python3 tools/png_to_tiles.py --bank 255 assets/maps/tileset.png src/track_tiles.c track_tile_data

# Ensure regeneration happens before ROM link if PNG is newer
$(TARGET): src/track_tiles.c

# src/player_sprite.c is checked into git so CI works without Python.
# Running `make src/player_sprite.c` (or plain `make`) regenerates it when needed.
src/player_sprite.c: assets/sprites/player_car.png tools/png_to_tiles.py
	python3 tools/png_to_tiles.py --bank 255 assets/sprites/player_car.png src/player_sprite.c player_tile_data

$(TARGET): src/player_sprite.c

# NPC portraits use --bank 255 (autobank). state_hub.c (bank 0) calls SET_BANK to
# load portrait tiles into VRAM. Bank-0 code may freely call SWITCH_ROM.
src/npc_mechanic_portrait.c: assets/sprites/npc_mechanic.png tools/png_to_tiles.py
	python3 tools/png_to_tiles.py --bank 255 assets/sprites/npc_mechanic.png src/npc_mechanic_portrait.c npc_mechanic_portrait

src/npc_trader_portrait.c: assets/sprites/npc_trader.png tools/png_to_tiles.py
	python3 tools/png_to_tiles.py --bank 255 assets/sprites/npc_trader.png src/npc_trader_portrait.c npc_trader_portrait

src/npc_drifter_portrait.c: assets/sprites/npc_drifter.png tools/png_to_tiles.py
	python3 tools/png_to_tiles.py --bank 255 assets/sprites/npc_drifter.png src/npc_drifter_portrait.c npc_drifter_portrait

$(TARGET): src/npc_mechanic_portrait.c src/npc_trader_portrait.c src/npc_drifter_portrait.c

# src/dialog_border_tiles.c is checked into git so CI works without Python.
# Run `make src/dialog_border_tiles.c` to regenerate from updated PNG.
src/dialog_border_tiles.c src/dialog_border_tiles.h: assets/sprites/dialog_border.png tools/png_to_tiles.py
	python3 tools/png_to_tiles.py --bank 255 assets/sprites/dialog_border.png src/dialog_border_tiles.c dialog_border_tiles

$(TARGET): src/dialog_border_tiles.c

# src/dialog_data.c and src/hub_data.c are checked into git so CI works without Python.
# Run `make dialog_data` to regenerate from updated JSON.
src/dialog_data.c src/hub_data.c: assets/dialog/npcs.json assets/dialog/hubs.json tools/dialog_to_c.py src/config.h
	python3 tools/dialog_to_c.py assets/dialog/npcs.json src/dialog_data.c \
		--hubs-json assets/dialog/hubs.json \
		--hub-out src/hub_data.c \
		--config-h src/config.h

dialog_data: src/dialog_data.c src/hub_data.c

$(TARGET): src/dialog_data.c

$(OBJ_DIR)/%.o: src/%.c | $(OBJ_DIR)
	$(LCC) $(CFLAGS) $(ROMFLAGS) -c -o $@ $<

$(TARGET): $(OBJS) | build bank-check
	$(LCC) $(CFLAGS) $(ROMFLAGS) -o $@ $(OBJS) -Wl-k$(CURDIR)/lib/hUGEDriver/gbdk -Wl-lhUGEDriver.lib

$(OBJ_DIR):
	mkdir -p $(OBJ_DIR)

build:
	mkdir -p build

test: $(TEST_SRCS) | build
	@for f in $(TEST_SRCS); do \
		name=$$(basename $$f .c); \
		echo "  CC  $$f"; \
		gcc $(TEST_FLAGS) $(UNITY_SRC) $(TEST_LIB_SRC) $(MOCK_SRCS) $$f -o build/$$name || exit 1; \
		echo "  RUN build/$$name"; \
		./build/$$name || exit 1; \
	done

# src/overmap_tiles.c is checked into git so CI works without Python/Aseprite.
src/overmap_tiles.c: assets/maps/overmap_tiles.png tools/png_to_tiles.py
	python3 tools/png_to_tiles.py --bank 255 assets/maps/overmap_tiles.png src/overmap_tiles.c overmap_tile_data

$(TARGET): src/overmap_tiles.c

# src/overmap_map.c is checked into git so CI works without Python/Tiled.
src/overmap_map.c: assets/maps/overmap.tmx tools/tmx_to_array_c.py
	python3 tools/tmx_to_array_c.py assets/maps/overmap.tmx src/overmap_map.c overmap_map config.h

$(TARGET): src/overmap_map.c

test-tools:
	PYTHONPATH=. python3 -m unittest tests.test_png_to_tiles tests.test_tmx_to_c tests.test_bank_check tests.test_bank_post_build tests.test_dialog_to_c -v

# Validate #pragma bank in src/*.c against bank-manifest.json — fails build on mismatch
bank-check:
	python3 tools/bank_check.py .

bank-post-build:
	python3 tools/bank_post_build.py .

memory-check:
	python3 tools/memory_check.py .

clean:
	rm -rf build/
