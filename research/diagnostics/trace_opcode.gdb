# Experimental x86_64 probe for the local PHP 5.2.17 build.
# zend_op.opcode is at byte 116; confirm with offsetof before reusing.
set pagination off
set breakpoint pending on
break zend_vm_set_opcode_handler
commands
silent
printf "[setter] opcode=%u ptr=%p caller=%p\n", *(unsigned char*)($rdi+116), $rdi, *(void**)$rsp
continue
end
run
