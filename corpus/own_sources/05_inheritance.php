<?php
class A { public function answer() { return 42; } }
class B extends A { public function answer() { return parent::answer() + 1; } }
