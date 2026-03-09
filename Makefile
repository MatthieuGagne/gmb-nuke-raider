GBDK_HOME ?= /opt/gbdk
LCC       := $(GBDK_HOME)/bin/lcc

CFLAGS    := -Wa-l -Wl-m -Wl-j
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

.PHONY: all clean test

all: $(TARGET)

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

clean:
	rm -rf build/
