# encoding: utf8

"""
CHIP-8 

https://en.wikipedia.org/wiki/CHIP-8
"""

import os
import sys
import time
import pygame
import pygame.locals

from random import randint

def log_error(fmt, *args):
    if args:
        print fmt % args
    else:
        print fmt

def log_info(fmt, *args):
    if args:
        print fmt % args
    else:
        print fmt

fonts = [
    0xF0, 0x90, 0x90, 0x90, 0xF0, # 0
    0x20, 0x60, 0x20, 0x20, 0x70, # 1
    0xF0, 0x10, 0xF0, 0x80, 0xF0, # 2
    0xF0, 0x10, 0xF0, 0x10, 0xF0, # 3
    0x90, 0x90, 0xF0, 0x10, 0x10, # 4
    0xF0, 0x80, 0xF0, 0x10, 0xF0, # 5
    0xF0, 0x80, 0xF0, 0x90, 0xF0, # 6
    0xF0, 0x10, 0x20, 0x40, 0x40, # 7
    0xF0, 0x90, 0xF0, 0x90, 0xF0, # 8
    0xF0, 0x90, 0xF0, 0x10, 0xF0, # 9
    0xF0, 0x90, 0xF0, 0x90, 0x90, # A
    0xE0, 0x90, 0xE0, 0x90, 0xE0, # B
    0xF0, 0x80, 0x80, 0x80, 0xF0, # C
    0xE0, 0x90, 0x90, 0x90, 0xE0, # D
    0xF0, 0x80, 0xF0, 0x80, 0xF0, # E
    0xF0, 0x80, 0xF0, 0x80, 0x80, # F
]

BLACK = (0xFF, 0xFF, 0xFF)

XXX = 64
YYY = 32

class Chip8(object):

    def __init__(self, ui):

        self.n = 0
        self.ui = ui

        self.pc = 0x200 # program counter start at 0x200

        self.opcode = 0 

        # The address register, which is named I, is 16 bits wide and is used with several opcodes that involve memory operations.
        self.I = 0 

        # CHIP-8 has 16 8-bit data registers named from V0 to VF. 
        # The VF register doubles as a flag for some instructions, thus it should be avoided. In addition operation VF is for carry flag. 
        # While in subtraction, it is the "no borrow" flag. In the draw instruction the VF is set upon pixel collision.
        self.V = bytearray(16)

        # The stack is only used to store return addresses when subroutines are called. 
        # The original 1802 version allocated 48 bytes for up to 24 levels of nesting; modern implementations normally have at least 16 levels.
        self.stack = []

        # CHIP-8 was most commonly implemented on 4K systems, such as the Cosmac VIP and the Telmac 1800. 
        # These machines had 4096 (0x1000) memory locations, all of which are 8 bits (a byte) which is where the term CHIP-8 originated. However, 
        # the CHIP-8 interpreter itself occupies the first 512 bytes of the memory space on these machines. 
        # For this reason, most programs written for the original system begin at memory location 512 (0x200) and do not access any of the memory below the location 512 (0x200). 
        # The uppermost 256 bytes (0xF00-0xFFF) are reserved for display refresh, and the 96 bytes below that (0xEA0-0xEFF) were reserved for call stack, internal use, and other variables.
        # In modern CHIP-8 implementations, where the interpreter is running natively outside the 4K memory space, there is no need for any of the lower 512 bytes memory space to be used, 
        # but it is common to store font data in those lower 512 bytes (0x000-0x200).
        self.memory = bytearray(4096)

        # load font set
        for i, V in enumerate(fonts):
            self.memory[i] = V


        # CHIP-8 has two timers. They both count down at 60 hertz, until they reach 0.
        # Delay timer: This timer is intended to be used for timing the events of games. Its value can be set and read.
        # Sound timer: This timer is used for sound effects. When its value is nonzero, a beeping sound is made.
        self.delay_timer = 0, 0
        self.sound_timer = 0

    def load_rom(self, file_path):
        with open(file_path, "rb") as rom_file:
            data = rom_file.read()
            length = len(data)
            assert(len(self.memory) - self.pc > length)
            for i in range(length):
                self.memory[i + self.pc] = data[i]
        log_info("load_rom %s %s", file_path, length)

    def emulate_cycle(self):
        V = self.V
        I = self.I
        memory = self.memory

        self.n += 1

        # 2 byte
        AX = memory[self.pc]
        YD = NN = memory[self.pc + 1]
        A = (AX & 0xF0) >> 4
        X = AX & 0x0F
        Y = (YD & 0xF0) >> 4
        D = YD & 0x0F
        NNN = (X << 8) | YD
        F = 0xF

        opcode = self.opcode =  AX << 8 | YD
        # log_info("execute %s %s %s %s", hex(AX), hex(YD), self.n, self.pc)
        self.pc += 2

        if A == 0x0:
            # 00E0	Display	disp_clear()	Clears the screen.
            if NNN == 0x0E0:
                self.ui.clear_screen()

            # 00EE	Flow	return;	Returns from a subroutine.
            elif NNN == 0x0EE:
                self.pc = self.stack.pop()

            else:
                log_error("unkown opcode %s", opcode)

        elif A == 0x1:
            # 1NNN	Flow	goto NNN;	Jumps to address NNN.
            self.pc = NNN

        elif A == 0x2:
            # 2NNN	Flow	*(0xNNN)()	Calls subroutine at NNN.
            self.stack.append(self.pc)
            self.pc = NNN

        elif A == 0x3:
            # 3XNN	Cond	if(Vx==NN)	Skips the next instruction if VX equals NN. (Usually the next instruction is a jump to skip a code block)
            if V[X] == NN:
                self.pc += 2

        elif A == 0x4:
            # 4XNN	Cond	if(Vx!=NN)	Skips the next instruction if VX doesn't equal NN. (Usually the next instruction is a jump to skip a code block)
            if V[X] != NN:
                self.pc += 2

        elif A == 0x5:
            # 5XY0	Cond	if(Vx==Vy)	Skips the next instruction if VX equals VY. (Usually the next instruction is a jump to skip a code block)
            if V[X] == V[Y]:
                self.pc += 2

        elif A == 0x9:
            # 9XY0	Cond	if(Vx!=Vy)	Skips the next instruction if VX doesn't equal VY. (Usually the next instruction is a jump to skip a code block)
            if V[X] != V[Y]:
                self.pc += 2

        elif A == 0x6:
            # 6XNN	Const	Vx = NN	Sets VX to NN.
            V[X] = NN

        elif A == 0x7:
            # 7XNN	Const	Vx += NN	Adds NN to VX. (Carry flag is not changed)
            if V[X] + NN > 0xFF:
                V[X] = (V[X] + NN) & 0xFF
            else:
                V[X] += NN

        elif A == 0x8:
            # 8XY0	Assign	Vx=Vy	Sets VX to the value of VY.
            if D == 0x0:
                V[X] = V[Y]

            # 8XY1	BitOp	Vx=Vx|Vy	Sets VX to VX or VY. (Bitwise OR operation)
            elif D == 0x1:
                V[X] |= V[Y]

            # 8XY2	BitOp	Vx=Vx&Vy	Sets VX to VX and VY. (Bitwise AND operation)
            elif D == 0x2:
                V[X] &= V[Y]

            # 8XY3	BitOp	Vx=Vx^Vy	Sets VX to VX xor VY.
            elif D == 0x3:
                V[X] ^= V[Y]

            # 8XY4	Math	Vx += Vy	Adds VY to VX. VF is set to 1 when there's a carry, and to 0 when there isn't.
            elif D == 0x4:
                if V[X] + V[Y] > 0xFF:
                    V[X] = (V[X] + V[Y]) & 0xFF
                    V[F] = 1
                else:
                    V[X] += V[Y]
                    V[F] = 0

            # 8XY5	Math	Vx -= Vy	VY is subtracted from VX. VF is set to 0 when there's a borrow, and 1 when there isn't.
            elif D == 0x5:
                if V[X] < V[Y]:
                    V[X] = V[Y] - V[X]
                    V[F] = 0
                else:
                    V[X] -= V[Y]
                    V[F] = 1

            # 8XY6	BitOp	Vx>>=1	Stores the least significant bit of VX in VF and then shifts VX to the right by 1.[2]
            elif D == 0x6:
                V[F] = V[X] & 0x1
                V[X] = V[Y] >> 1

            # 8XY7	Math	Vx=Vy-Vx	Sets VX to VY minus VX. VF is set to 0 when there's a borrow, and 1 when there isn't.
            elif D == 0x7:
                if V[Y] > V[X]:
                    V[X] = V[Y] - V[X]
                    V[F] = 1
                else:
                    V[X] = V[X] - V[Y]
                    V[F] = 0

            # 8XYE	BitOp	Vx<<=1	Stores the most significant bit of VX in VF and then shifts VX to the left by 1.[3]
            elif D == 0xE:
                V[F] = V[X] >> 7 & 0x1
                V[X] = V[X] << 1 & 0xFF

            else:
                log_error("unkown opcode %s", opcode)

        elif A == 0xA:
            # ANNN	MEM	I = NNN	Sets I to the address NNN.
            self.I = NNN

        elif A == 0xB:
            # BNNN	Flow	PC=V0+NNN	Jumps to the address NNN plus V0.
            self.pc = (NNN + V[0]) & 0xFFFF

        elif A == 0xC:
            # CXNN	Rand	Vx=rand()&NN	Sets VX to the result of a bitwise and operation on a random number (Typically: 0 to 255) and NN.
            V[X] = randint(0, 0xFF) & NN

        elif A == 0xD:
            # DXYN	Disp	draw(Vx,Vy,N)	Draws a sprite at coordinate (VX, VY) that has a width of 8 pixels and a height of N pixels. 
            # Each row of 8 pixels is read as bit-coded starting from memory location I; 
            # I value doesn’t change after the execution of this instruction. 
            # As described above, VF is set to 1 if any screen pixels are flipped from set to unset when the sprite is drawn, and to 0 if that doesn’t happen
            y = V[Y]
            height = D
            erase = False

            for line in memory[I: I + height]:
                # a byte as a line, a bit as a pixel
                # draw a line here
                x = V[X]
                for _ in range(8):
                    if line >> 7 & 0x1:
                        erase |= self.ui.draw_pixel(x % XXX, y % YYY)
                    line <<= 1
                    x += 1
                y += 1

            self.ui.update()
            V[F] = 1 if erase else 0

        elif A == 0xE:

            # EX9E	KeyOp	if(key()==Vx)	Skips the next instruction if the key stored in VX is pressed. (Usually the next instruction is a jump to skip a code block)
            if YD == 0x9E:
                if self.ui.keyboard[V[X]]:
                    self.pc += 2

            # EXA1	KeyOp	if(key()!=Vx)	Skips the next instruction if the key stored in VX isn't pressed. (Usually the next instruction is a jump to skip a code block)
            elif YD == 0xA1:
                if not self.ui.keyboard[V[X]]:
                    self.pc += 2

            else:
                log_error("unkown opcode %s", opcode)

        # 下面的还没有检查

        elif A == 0xF:

            # FX07	Timer	Vx = get_delay()	Sets VX to the value of the delay timer.
            if YD == 0x07:
                value, start = self.delay_timer
                current = int(value - (time.time() - start) * 60)
                V[X] = max(current, 0)

            # FX0A	KeyOp	Vx = get_key()	A key press is awaited, and then stored in VX. (Blocking Operation. All instruction halted until next key event)
            elif YD == 0x0A:
                i = self.ui.wait_key_event()
                V[X] = i

            # FX15	Timer	delay_timer(Vx)	Sets the delay timer to VX.
            elif YD == 0x15:
                self.delay_timer = V[X], time.time()

            # FX18	Sound	sound_timer(Vx)	Sets the sound timer to VX.
            elif YD == 0x18:
                pass

            # FX1E	MEM	I +=Vx	Adds VX to I.[4]
            # VF is set to 1 when there is a range overflow (I+VX>0xFFF), and to 0 when there isn't. 
            # This is an undocumented feature of the CHIP-8 and used by the Spacefight 2091! game.
            elif YD == 0x1E:
                if I + V[X] > 0xFFF:
                    V[F] = 1
                else:
                    V[F] = 0
                self.I = (V[X] + I) & 0xFFFF

            # FX29	MEM	I=sprite_addr[Vx]	Sets I to the location of the sprite for the character in VX. Characters 0-F (in hexadecimal) are represented by a 4x5 font.
            elif YD == 0x29:
                self.I = V[X] * 0x5

            # FX33	BCD	set_BCD(Vx);
            # *(I+0)=BCD(3);
            # *(I+1)=BCD(2);
            # *(I+2)=BCD(1);
            # Stores the binary-coded decimal representation of VX, with the most significant of three digits at the address in I, the middle digit at I plus 1, and the least significant digit at I plus 2. 
            # (In other words, take the decimal representation of VX, place the hundreds digit in memory at location in I, the tens digit at location I+1, and the ones digit at location I+2.)
            elif YD == 0x33:
                memory[I] = V[X] / 100
                memory[I + 1] = V[X] / 10 % 10
                memory[I + 2] = V[X] % 100

            # FX55	MEM	reg_dump(Vx,&I)	Stores V0 to VX (including VX) in memory starting at address I. 
            # The offset from I is increased by 1 for each value written, but I itself is left unmodified.
            elif YD == 0x55:
                for i in range(X + 1):
                    memory[I + i] = V[i]

            # FX65	MEM	reg_load(Vx,&I)	Fills V0 to VX (including VX) with values from memory starting at address I. 
            # The offset from I is increased by 1 for each value written, but I itself is left unmodified.
            elif YD == 0x65:
                for i in range(X + 1):
                    V[i] = memory[I + i]

            else:
                log_error("unkown opcode %s", opcode)

WHITE = (0, 0, 0)

class UI(object):

    def __init__(self):
        self.X = XXX
        self.Y = YYY
        self.factor = 10
        self.keyboard = [False] * 16

        self.screen = pygame.display.set_mode((self.X * self.factor, self.Y * self.factor))
        self.interval = 0.01

        self.clear_screen()

        import pygame.locals as l
        self.keys = (
            l.K_x, 
            l.K_1, l.K_2, l.K_3,
            l.K_q, l.K_w, l.K_e, 
            l.K_a, l.K_s, l.K_d, 
            l.K_z, l.K_c, 
            l.K_4, l.K_r, l.K_f, l.K_v, 
        )

    def clear_screen(self):
        self.buffer = [[False] * self.Y for _ in range(self.X)]
        self.screen.fill(BLACK, (0, 0, self.X * self.factor, self.Y * self.factor))

    def update(self):
        pygame.display.flip()

    def handle_input_event(self):
        for event in pygame.event.get():
            if event.type in (pygame.KEYUP, pygame.KEYDOWN):
                if event.key == pygame.locals.K_ESCAPE:
                    sys.exit(0)
                elif event.key in self.keys:
                    i = self.keys.index(event.key)
                    self.keyboard[i] = event.type == pygame.KEYDOWN
                    if event.type == pygame.KEYDOWN:
                        return i

    def wait_key_event(self, key):
        while True:
            i = self.handle_input_event()
            if i is not None:
                return i
            time.sleep(self.interval)

    def draw_pixel(self, x, y):
        old = self.buffer[x][y]
        new = not old
        self.buffer[x][y] = new
        color = WHITE if new else BLACK
        factor = self.factor
        self.screen.fill(color, (x *factor, y * factor, factor, factor))
        return old

    def beef(self):
        log_info("BEEF")

def main():
    ui = UI()
    c = Chip8(ui)
    c.load_rom(sys.argv[1])
    while True:
        ui.handle_input_event()
        c.emulate_cycle()
        time.sleep(0.01)

main()

