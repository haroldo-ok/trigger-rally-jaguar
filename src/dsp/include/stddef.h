/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef TR_JRISC_STDDEF_H
#define TR_JRISC_STDDEF_H
typedef unsigned long size_t;
typedef signed long ptrdiff_t;
#define NULL ((void *)0)
#define offsetof(type,member) ((size_t)&(((type *)0)->member))
#endif
