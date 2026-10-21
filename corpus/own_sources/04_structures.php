<?php
function unpack_pair($input) {
  list($a, $b) = $input;
  if (isset($input[0]) && !empty($input[1])) { return $a; }
  return $b;
}
try { throw new Exception('demo'); } catch (Exception $e) { echo 'caught'; }
