SHELL := /bin/bash
.DEFAULT_GOAL := all
ROOT := $(CURDIR)
LYXASS ?= $(ROOT)/vendor/lyxass/lyxass
BJL_ROOT ?= $(ROOT)/vendor/new_bjl
TR_PUBLIC ?= $(if $(wildcard ../upstream/TriggerRally/server/public),$(abspath ../upstream/TriggerRally/server/public),$(ROOT)/.cache/TriggerRally/server/public)
CC68 ?= m68k-linux-gnu-gcc
OBJCOPY ?= m68k-linux-gnu-objcopy
CORE ?= $(ROOT)/vendor/bin/virtualjaguar_libretro.so
JRISC_TOOLS := $(ROOT)/.cache/jrisc/bin
JRISC_CC := $(JRISC_TOOLS)/vbccjrisc
$(JRISC_CC): tools/build_jrisc_tools.py tools/patches/vbcc-jrisc-binary32.patch $(wildcard vendor/jrisc/*)
	python3 tools/build_jrisc_tools.py
src/render_tables.h: tools/make_render_tables.py
	python3 tools/make_render_tables.py
DSP_INPUTS := src/main.c src/physics.c src/render_math.c $(wildcard src/*.h src/dsp/*.c src/dsp/*.s src/dsp/*.ld src/dsp/include/*.h)
assets/dsp_game.bin src/dsp/image.h &: $(DSP_INPUTS) tools/build_dsp_game.py assets/gpu.bin src/font8x8.bin $(JRISC_CC)
	python3 tools/build_dsp_game.py

CFLAGS := -m68000 -msoft-float --param=min-pagesize=0 -O2 -ffast-math -std=c11 -ffreestanding -fno-builtin -fno-pie -fno-stack-protector -fomit-frame-pointer -ffunction-sections -fdata-sections -Wall -Wextra -Wno-misleading-indentation
LDFLAGS := -m68000 -nostdlib -static -no-pie -Wl,--build-id=none,--gc-sections,-T,src/jaguar.ld
export BJL_ROOT
.PHONY: test-driving all assets regenerate-assets fetch-upstream clean test test-smoke test-core bootstrap test-black-screen test-desktop test-e2e release
all: releases/trigger-rally-jaguar.j64
assets: assets/assets.bin
assets/assets.bin assets/asset_ids.h assets/asset_ids.inc &: tools/convert_assets.py tools/cry_palette.json src/data.h
	python3 tools/convert_assets.py --public "$(TR_PUBLIC)"
src/memory.h src/gpu/memory.inc &: tools/memory_map.py
	python3 tools/memory_map.py
$(LYXASS): $(wildcard vendor/lyxass/*.c vendor/lyxass/*.h) vendor/lyxass/Makefile
	$(MAKE) -C $(dir $(LYXASS))
OBL := src/gpu/obl0_50.bin src/gpu/obl1_50.bin src/gpu/obl0_60.bin src/gpu/obl1_60.bin
$(OBL) &: tools/make_obl.py src/gpu/video.h
	python3 tools/make_obl.py
assets/gpu.bin: $(OBL) $(wildcard src/gpu/*.inc src/gpu/*.h src/gpu/*.js src/gpu/obl*.bin) src/gpu/memory.inc assets/asset_ids.inc $(LYXASS)
	cd src/gpu && $(abspath $(LYXASS)) -d -s -o ../../assets/gpu.bin rally.js
assets/audio.bin: src/gpu/audio.js $(LYXASS)
	cd src/gpu && $(abspath $(LYXASS)) -d -s -o ../../assets/audio.bin audio.js
artifacts/%.o: src/%.c $(wildcard src/*.h) assets/asset_ids.h src/memory.h Makefile
	mkdir -p artifacts
	$(CC68) $(CFLAGS) -c $< -o $@
artifacts/start.o: src/start.S assets/gpu.bin assets/audio.bin src/font8x8.bin Makefile
	mkdir -p artifacts
	$(CC68) -m68000 -c $< -o $@
RT_FUNCTIONS := mulsi3 udivsi3 divsi3 umodsi3 modsi3 float floatex eqsf2 nesf2 gtsf2 gesf2 ltsf2 lesf2
RT_OBJECTS := $(addprefix artifacts/rt_,$(addsuffix .o,$(RT_FUNCTIONS)))
artifacts/rt_%.o: vendor/lb1sf68.S Makefile
	mkdir -p artifacts
	$(CC68) -m68000 -msoft-float -fno-pic -fno-pie -DL_$* -c $< -o $@
artifacts/host.o: src/host.c src/dsp/image.h Makefile
	mkdir -p artifacts
	$(CC68) $(CFLAGS) -c $< -o $@
artifacts/dsp_blob.o: src/dsp_blob.S assets/dsp_game.bin Makefile
	mkdir -p artifacts
	$(CC68) -m68000 -c $< -o $@
artifacts/program.elf: artifacts/start.o artifacts/host.o artifacts/dsp_blob.o src/jaguar.ld Makefile
	$(CC68) $(LDFLAGS) -Wl,-Map,$(@:.elf=.map) artifacts/start.o artifacts/host.o artifacts/dsp_blob.o -o $@
	m68k-linux-gnu-size $@
artifacts/program.bin: artifacts/program.elf
	$(OBJCOPY) -O binary $< $@
artifacts/cartboot.o: src/cartboot.S Makefile
	mkdir -p artifacts
	$(CC68) -m68000 -c $< -o $@
artifacts/cartboot.bin: artifacts/cartboot.o
	$(CC68) -m68000 -nostdlib -static -no-pie -Wl,--build-id=none,-Ttext=0x83f000,-e,cart_boot,--oformat=binary $< -o $@
releases/trigger-rally-jaguar.j64: artifacts/program.bin artifacts/cartboot.bin assets/assets.bin src/boot.XXX tools/pack_rom.py tools/build_inputs.py
	python3 tools/pack_rom.py
artifacts/math.o: tests/math_kernel.c Makefile
	mkdir -p artifacts
	$(CC68) $(CFLAGS) -c $< -o $@
artifacts/math.elf: artifacts/start.o artifacts/math.o artifacts/softfloat.o $(RT_OBJECTS) src/jaguar.ld Makefile
	$(CC68) $(LDFLAGS) -Wl,-Map,$(@:.elf=.map) artifacts/start.o artifacts/math.o artifacts/softfloat.o $(RT_OBJECTS) -o $@
artifacts/math.bin: artifacts/math.elf
	$(OBJCOPY) -O binary $< $@
fetch-upstream:
	python3 tools/fetch_upstream.py
regenerate-assets:
	python3 tools/convert_assets.py --public "$(TR_PUBLIC)"
bootstrap: $(LYXASS)
	python3 tools/rebuild_bootstrap.py --assembler "$(LYXASS)" --sdk "$(BJL_ROOT)"
test-core:
	mkdir -p .cache
	tar -xzf vendor/virtualjaguar-libretro-source.tar.gz -C .cache
	$(MAKE) -C .cache/virtualjaguar-libretro -j4 TEST_EXPORTS=1 LTO=0
	mkdir -p vendor/bin
	cp .cache/virtualjaguar-libretro/virtualjaguar_libretro.so vendor/bin/
test-black-screen: all
	python3 tests/check_assets.py
	python3 tests/check_hud_decoder.py
	python3 tests/black_screen_suite.py --core "$(CORE)"
	python3 tools/check_bios_path_regression.py --core "$(CORE)"
test-driving: all
	python3 tests/playability_suite.py --core "$(CORE)"
test-e2e: test-black-screen
test-desktop: all
	python3 tests/e2e_desktop_virtual_jaguar.py --bios off --output artifacts/e2e-desktop-ntsc-bios-off
test-smoke: all
	python3 tests/check_assets.py
	python3 tests/check_hud_decoder.py
	python3 tests/check_math.py --core "$(CORE)"
	python3 tests/black_screen_suite.py --core "$(CORE)" --smoke
test: all
	python3 tests/check_assets.py
	python3 tests/check_hud_decoder.py
	python3 tests/check_math.py --core "$(CORE)"
	python3 tests/check_dsp_math.py --core "$(CORE)"
	python3 tests/playability_suite.py --core "$(CORE)"
	python3 tests/e2e_virtual_jaguar.py --core "$(CORE)" --bios on --blitter accurate
	python3 tests/e2e_virtual_jaguar.py --core "$(CORE)" --bios off --blitter accurate --output artifacts/e2e-ntsc-bios-off
	python3 tests/black_screen_suite.py --core "$(CORE)"
	python3 tools/check_bios_path_regression.py --core "$(CORE)"
release: all
	python3 tools/make_report.py
	python3 tools/make_release.py
clean:
	mkdir -p artifacts
	find artifacts -maxdepth 1 -type f \( -name '*.o' -o -name '*.elf' -o -name '*.map' -o -name 'program.bin' -o -name 'math.bin' -o -name 'cartboot.bin' \) -delete
	rm -f $(OBL) assets/gpu.bin assets/audio.bin assets/dsp_game.bin src/dsp/image.h releases/trigger-rally-jaguar.j64
