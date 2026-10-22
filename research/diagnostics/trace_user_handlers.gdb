# Experimental x86_64 trace of user opcode registrations during PHP startup.
set pagination off
set breakpoint pending on
break zend_set_user_opcode_handler
commands
silent
printf "[register] opcode=%u handler=%p caller=%p\n", (unsigned int)$rdi, $rsi, *(void**)$rsp
continue
end
run
