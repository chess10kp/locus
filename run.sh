# GTK4 Layer Shell requires LD_PRELOAD for correct linking order with libwayland
# This may cause memory corruption issues in some versions of GTK4 Layer Shell
# See: https://github.com/wmww/gtk4-layer-shell/blob/main/linking.md
#
# Workaround for malloc corruption with Python 3.13:
GTK_DEBUG=all MALLOC_CHECK_=0 MALLOC_PERTURB_=0 LD_PRELOAD=/usr/lib/libgtk4-layer-shell.so PWD=/home/sigma/projects/repos/locus uv run python ~/projects/repos/locus/main.py & disown
