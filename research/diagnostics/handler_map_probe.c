/* Experimental, compile-only research probe for the PHP 5.2.17 Zend VM.
 * Enumerates handler addresses without executing the protected script.
 * A shared handler address does not prove a unique opcode or its semantics.
 */
#include "php.h"
#include "zend_extensions.h"
#include "zend_vm.h"
#include <stdio.h>

static void map_op_array(zend_op_array *array)
{
    zend_uint i;
    fprintf(stderr, "[group] name=%s last=%u\n", array->function_name ? array->function_name : "<main>", array->last);
    for (i = 0; i < array->last; ++i) {
        const zend_op *op = &array->opcodes[i];
        zend_op work;
        unsigned int candidate;
        int matches = 0;
        opcode_handler_t target = op->handler;
        const char *source = "observed";
        if (!target) {
            work = *op;
            zend_vm_set_opcode_handler(&work);
            target = work.handler;
            source = "computed";
        }
        fprintf(stderr, "[map] index=%u opcode=%u op1_type=%d op2_type=%d handler=%p source=%s candidates=",
                i, op->opcode, op->op1.op_type, op->op2.op_type, (void *)target, source);
        for (candidate = 0; candidate < 256; ++candidate) {
            work = *op;
            work.opcode = candidate;
            zend_vm_set_opcode_handler(&work);
            if (work.handler == target) {
                fprintf(stderr, "%s%u", matches ? "," : "", candidate);
                ++matches;
            }
        }
        fprintf(stderr, " count=%d\n", matches);
    }
}

zend_extension_version_info extension_version_info = { ZEND_EXTENSION_API_NO, ZEND_VERSION, 0, 0 };
zend_extension zend_extension_entry = {
    .name = "zend-php52-handler-map-probe",
    .version = "0.1",
    .author = "local research",
    .op_array_handler = map_op_array
};
