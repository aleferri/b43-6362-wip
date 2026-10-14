/* SPDX-License-Identifier: GPL-2.0
 * Il minimo per compilare lib/math/cordic.c in userspace: le macro di modulo
 * non fanno niente qui.
 */
#ifndef _TEST_LINUX_MODULE_H
#define _TEST_LINUX_MODULE_H
#define EXPORT_SYMBOL(x)
#define EXPORT_SYMBOL_GPL(x)
#define MODULE_DESCRIPTION(x)
#define MODULE_AUTHOR(x)
#define MODULE_LICENSE(x)
#endif
