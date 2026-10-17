OUTPUT_FORMAT("elf32-m68k")
OUTPUT_ARCH(m68k)
ENTRY(_start)
SECTIONS {
    . = 0x10000;
    .boot : { KEEP(*(.boot)) }
    .text : { *(.text .text.*) }
    ASSERT(. <= 0x11bf0,"68000 host overlaps compatibility entry")
    . = 0x11bf0;
    .compat : { KEEP(*(.compat.boot)) }
    .rodata : ALIGN(8) { *(.rodata .rodata.*) }
    .data : ALIGN(8) { *(.data .data.*) }
    . = ALIGN(8);
    __image_end = .;
    __bss_start = .;
    .bss (NOLOAD) : { *(.bss .bss.* COMMON) }
    . = ALIGN(8);
    __bss_end = .;
    /DISCARD/ : { *(.comment .eh_frame .note*) }
    ASSERT(__bss_end < 0x40000,"68000 code/BSS overlaps terrain RAM")
}
