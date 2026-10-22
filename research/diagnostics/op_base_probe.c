/* Experimental PHP 5.2.17 compile-only probe: report opcode array bases.
 * Compare addresses only within the same process; ASLR changes them each run.
 */
#include "php.h"
#include "zend_extensions.h"
#include <stdio.h>
static void report(zend_op_array *a) {
    fprintf(stderr, "[base] name=%s opcodes=%p last=%u\n", a->function_name ? a->function_name : "<main>", (void *)a->opcodes, a->last);
}
zend_extension_version_info extension_version_info = { ZEND_EXTENSION_API_NO, ZEND_VERSION, 0, 0 };
zend_extension zend_extension_entry = {
    .name = "zend-php52-op-base-probe", .version = "0.1", .author = "local research", .op_array_handler = report
};
