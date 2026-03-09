GBDK_HOME ?= /opt/gbdk
LCC       := $(GBDK_HOME)/bin/lcc

CFLAGS    := -Wa-l -Wl-m -Wl-j
ifeq ($(DEBUG),1)
CFLAGS += -DDEBUG
endif
ROMFLAGS  := -Wm-yc -Wm-yt1 -Wm-yn"WSTLND RACER"

TARGET    := build/wasteland-racer.gb
OBJ_DIR   := build/obj

SRCS      := $(wildcard src/*.c)
OBJS      := $(patsubst src/%.c,$(OBJ_DIR)/%.o,$(SRCS))

UNITY_SRC    := tests/unity/src/unity.c
TEST_SRCS    := $(wildcard tests/test_*.c)
TEST_FLAGS   := -Itests/mocks -Itests/unity/src -Isrc -Wall -Wextra
TEST_LIB_SRC := $(filter-out src/main.c,$(wildcard src/*.c))
MOCK_SRCS    := $(wildcard tests/mocks/*.c)

.PHONY: all clean test test-tools

all: $(TARGET)

# ── Generated sources ─────────────────────────────────────────────────────────
# src/track_map.c is checked into git so CI works without Python/Tiled.
# Running `make src/track_map.c` (or plain `make`) regenerates it when needed.
src/track_map.c: assets/maps/track.tmx tools/tmx_to_c.py
	python3 tools/tmx_to_c.py assets/maps/track.tmx src/track_map.c

# Ensure regeneration happens before ROM link if TMX is newer
$(TARGET): src/track_map.c

# src/track_tiles.c is checked into git so CI works without Python.
# Running `make src/track_tiles.c` (or plain `make`) regenerates it when needed.
src/track_tiles.c: assets/maps/tileset.png tools/png_to_tiles.py
	python3 tools/png_to_tiles.py assets/maps/tileset.png src/track_tiles.c track_tile_data

# Ensure regeneration happens before ROM link if PNG is newer
$(TARGET): src/track_tiles.c

$(OBJ_DIR)/%.o: src/%.c | $(OBJ_DIR)
	$(LCC) $(CFLAGS) $(ROMFLAGS) -c -o $@ $<

$(TARGET): $(OBJS) | build
	$(LCC) $(CFLAGS) $(ROMFLAGS) -o $@ $(OBJS)

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

test-tools:
	PYTHONPATH=. python3 -m unittest tests.test_sprite_editor tests.test_png_to_tiles -v

clean:
	rm -rf build/
