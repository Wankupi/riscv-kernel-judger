
static/boot/boot.scr.uimg: static/boot/boot.scr
	mkimage -A riscv -T script -C none -n "StarFive boot script" -d $< $@
