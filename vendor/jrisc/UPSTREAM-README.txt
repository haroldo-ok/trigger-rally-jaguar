vbcc jrisc preview 1

This is a port of the vbcc compiler to the Atari Jaguar architecture. It
contains a compiler, assembler, linker and a port of a C Library.

A few of the good things:

- compiler is under active development
- supports GPU/DSP/M68k
- supports workarounds for running RISC code from main memory
- supports automated banking into local memory
- tbc ...

This archive contains binaries for Windows and Linux x86 (statically
linked). A sample directory with a few small test cases is also included.

To use the compiler on Windows:

  set VBCC=<path-to-vbcc-dir>
  set PATH=%VBCC%\bin;%PATH%

On Linux, use something like:

  export VBCC=<path-to-vbcc-dir>
  export PATH=$VBCC/bin:$PATH

Compiling works pretty much like most compilers, e.g.:

  vc file.c -o binary

Choose a different target confguration with +<cfg>:

  vc +jriscbin file.c -o file.bin


Further information on vbcc can be found on

  http://www.compilers.de/vbcc

and in the vbcc.pdf included here. Apart from the general sections on
the compiler, be sure to have a look at the ones on the JRISC backend
and the JRISC/Jaguar part of the C library.


LEGAL

Please consult the vbcc.pdf regarding terms of usage.


For questions, results etc., reach me at: vb@compilers.de


Volker Barthelmann
