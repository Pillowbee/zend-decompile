<?php
function choose($x) {
    if ($x > 2) { return 1; }
    switch ($x) { case 1: return 2; default: return 3; }
}
for ($i = 0; $i < 3; $i++) { echo $i; }
