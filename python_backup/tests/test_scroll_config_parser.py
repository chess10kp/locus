"""Unit tests for scroll config parser."""

import tempfile
import os
from utils.scroll_config_parser import ScrollConfigParser


class TestScrollConfigParser:
    def test_simple_bindsym(self):
        """Test parsing simple bindsym."""
        config = """
bindsym $mod+Return exec foot
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".config", delete=False) as f:
            f.write(config)
            f.flush()
            parser = ScrollConfigParser(f.name)
            bindings = parser.parse()

        os.unlink(f.name)

        assert "" in bindings
        assert len(bindings[""]) == 1
        binding = bindings[""][0]
        assert binding.keys == "$mod+Return"  # Variables not expanded yet without set
        assert binding.command == "exec foot"

    def test_variable_parsing(self):
        """Test variable definition parsing."""
        config = """
set $mod Mod4
set $term foot
bindsym $mod+Return exec $term
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".config", delete=False) as f:
            f.write(config)
            f.flush()
            parser = ScrollConfigParser(f.name)
            bindings = parser.parse()

        os.unlink(f.name)

        binding = bindings[""][0]
        assert binding.keys == "Mod4+Return"  # Variable expanded
        assert binding.command == "exec foot"

    def test_mode_blocks(self):
        """Test parsing mode blocks."""
        config = """
bindsym $mod+Return exec foot
mode "resize" {
    bindsym $left resize shrink width 20px
    bindsym $right resize grow width 20px
}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".config", delete=False) as f:
            f.write(config)
            f.flush()
            parser = ScrollConfigParser(f.name)
            bindings = parser.parse()

        os.unlink(f.name)

        assert "" in bindings
        assert "resize" in bindings
        assert len(bindings[""]) == 1
        assert len(bindings["resize"]) == 2

    def test_flags(self):
        """Test parsing flags."""
        config = """
bindsym --no-repeat $mod+slash jump
bindsym --locked --no-warn $mod+x exec foot
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".config", delete=False) as f:
            f.write(config)
            f.flush()
            parser = ScrollConfigParser(f.name)
            bindings = parser.parse()

        os.unlink(f.name)

        assert bindings[""][0].flags == ["--no-repeat"]
        assert bindings[""][1].flags == ["--locked", "--no-warn"]

    def test_multiline_bindsym(self):
        """Test parsing multiline bindsym blocks."""
        config = """
bindsym {
    $mod+Return exec foot
    $mod+d exec dmenu
}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".config", delete=False) as f:
            f.write(config)
            f.flush()
            parser = ScrollConfigParser(f.name)
            bindings = parser.parse()

        os.unlink(f.name)

        assert len(bindings[""]) == 2

    def test_continuation_lines(self):
        """Test line continuation with backslash."""
        config = """
bindsym $mod+Return exec foot --option \\
    --another-option
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".config", delete=False) as f:
            f.write(config)
            f.flush()
            parser = ScrollConfigParser(f.name)
            bindings = parser.parse()

        os.unlink(f.name)

        assert len(bindings[""]) == 1

    def test_meaningful_command_extraction(self):
        """Test extraction of meaningful command."""
        config = """
bindsym $mod+m exec amixer set Master toggle && ~/.config/scripts/showstuff vol alsa
bindsym $mod+s exec foot; mode "default"
bindsym $mod+Return exec foot
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".config", delete=False) as f:
            f.write(config)
            f.flush()
            parser = ScrollConfigParser(f.name)
            bindings = parser.parse()

        os.unlink(f.name)

        # First binding: show just "exec amixer"
        assert "exec amixer" in bindings[""][0].meaningful_command
        # Second binding: mode command removed
        assert "mode" not in bindings[""][1].meaningful_command.lower()
        # Third binding: unchanged
        assert bindings[""][2].meaningful_command == "exec foot"

    def test_skip_comments_and_empty_lines(self):
        """Test that comments and empty lines are skipped."""
        config = """
# This is a comment
set $mod Mod4

bindsym $mod+Return exec foot

# Another comment
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".config", delete=False) as f:
            f.write(config)
            f.flush()
            parser = ScrollConfigParser(f.name)
            bindings = parser.parse()

        os.unlink(f.name)

        assert len(bindings[""]) == 1

    def test_mode_trigger_bindings_included(self):
        """Test that bindings that trigger modes are included."""
        config = """
bindsym $mod+s mode "script"
mode "script" {
    bindsym r mode "default"
}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".config", delete=False) as f:
            f.write(config)
            f.flush()
            parser = ScrollConfigParser(f.name)
            bindings = parser.parse()

        os.unlink(f.name)

        # Mode trigger binding should be included
        assert len(bindings[""]) == 1
        assert "mode" in bindings[""][0].command
        # Mode bindings included
        assert len(bindings["script"]) == 1

    def test_nested_blocks(self):
        """Test handling of nested blocks (should skip non-bindsym content)."""
        config = """
input "type:keyboard" {
    xkb_layout us
}

bindsym $mod+Return exec foot

mode "test" {
    bindsym $mod+q kill
}

exec foot
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".config", delete=False) as f:
            f.write(config)
            f.flush()
            parser = ScrollConfigParser(f.name)
            bindings = parser.parse()

        os.unlink(f.name)

        assert len(bindings[""]) == 1  # Only bindsym, not exec
        assert len(bindings["test"]) == 1

    def test_config_path_detection(self):
        """Test automatic config path detection."""
        # Should find the real config file
        parser = ScrollConfigParser()
        assert parser.config_path.endswith("config")
