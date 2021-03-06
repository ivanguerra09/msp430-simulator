#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
##  disasm.py
#
#  Copyright 2017 Unknown <root@hp425>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#

from memory import Memory, MemoryException
from instructions_utils import simulate_rrc_instruction, simulate_rra_instruction, simulate_push_instruction, simulate_swpb_instruction, simulate_sxt_instruction, simulate_call_instruction
                            
class Simulator():
    JNZ, JZ, JNC, JC, JGE, JN, JL, JMP = range(8)
    MOV, ADD, ADDC, SUBC, SUB, CMP, DADD, BIT, BIC, BIS, XOR, AND = range(12)
    RRC, SWPB, RRA, SXT, PUSH, CALL, RETI, NOP = range(8)

    def __init__(self, mem, regs):
        self.mem = mem
        self.regs = regs

    def one_step(self, addr):
        """ Ejecuta la instruccion ubicada en la memoria ROM en la
            direccion <addr>.
            Retorna el PC nuevo
        """
        self.addr = addr
        self.registers = self.regs.get_registers()

        opcode = self.mem.load_word_at(self.addr)
        
        if opcode == None:
            return 
        
        if self.addr >= 0xffc0:          # Estamos en la table de interrupciones?
            return opcode

        for mask, value, optype, opd in (
                    (0xff80, 0x1000, self.RRC,     self.opd_single_type1),
                    (0xff80, 0x1080, self.SWPB,    self.opd_single_type2),
                    (0xff80, 0x1100, self.RRA,     self.opd_single_type1),
                    (0xff80, 0x1180, self.SXT,     self.opd_single_type2),
                    (0xff80, 0x1200, self.PUSH,    self.opd_single_type1),
                    (0xff80, 0x1280, self.CALL,    self.opd_single_type2),
                    (0xffff, 0x1300, self.RETI,    self.opd_single_reti),

                    (0xfc00, 0x2000, self.JNZ,     self.opd_jump),
                    (0xfc00, 0x2400, self.JZ,      self.opd_jump),
                    (0xfc00, 0x2800, self.JNC,     self.opd_jump),
                    (0xfc00, 0x2c00, self.JC,      self.opd_jump),
                    (0xfc00, 0x3000, self.JN,      self.opd_jump),
                    (0xfc00, 0x3400, self.JGE,     self.opd_jump),
                    (0xfc00, 0x3800, self.JL,      self.opd_jump),
                    (0xfc00, 0x3c00, self.JMP,     self.opd_jump),

                    (0xf000, 0x4000, self.MOV,     self.opd_double),
                    (0xf000, 0x5000, self.ADD,     self.opd_double),
                    (0xf000, 0x6000, self.ADDC,    self.opd_double),
                    (0xf000, 0x7000, self.SUBC,    self.opd_double),
                    (0xf000, 0x8000, self.SUB,     self.opd_double),
                    (0xf000, 0x9000, self.CMP,     self.opd_double),
                    (0xf000, 0xa000, self.DADD,    self.opd_double),
                    (0xf000, 0xb000, self.BIT,     self.opd_double),
                    (0xf000, 0xc000, self.BIC,     self.opd_double),
                    (0xf000, 0xd000, self.BIS,     self.opd_double),
                    (0xf000, 0xe000, self.XOR,     self.opd_double),
                    (0xf000, 0xf000, self.AND,     self.opd_double),

                    (0x0000, 0x0000, self.NOP,     self.opd_single_reti)):

            if (opcode & mask) == value:
                self.addr += 2
                newpc = opd(self.addr, opcode, optype)
                return newpc

    def opc_register(self, opc):    return opc & 0x000f
    def opc_As(self, opc):          return (opc >> 4) & 0x0003
    def opc_Byte(self, opc):        return (opc & 0x0040) != 0
    def opc_destination(self, opc): return opc & 0x000f
    def opc_Ad(self, opc):          return (opc >> 7) & 0x0001
    def opc_source(self, opc):      return (opc >> 8) & 0x000f
    def opc_suffix(self, opc):      return '.b' if self.opc_Byte(opc) else ''

    #
    #   Instrucciones de simple operando
    #

    def opd_single_type1(self, addr, opcode, opcstr):
        """ Desensamblar instruccion RRC, RRA, PUSH """
        As = self.opc_As(opcode)
        Rs = self.opc_source(opcode)

        # Abreviamos el numero de registro
        regnr = self.opc_register(opcode)

        # Acordarse del estado del CY en ST
        cy = self.regs.get_SR('C')

        if As == 0:                                             # modo por registro

            if opcstr == 0: # Instruccion RRC.w o RRC.b
                simulate_rrc_instruction(self, regnr, opcode)
            elif opcstr == 2: # Instruccion RRA.w o RRA.b
                simulate_rra_instruction(self, regnr, opcode)
            elif opcstr == 4: # Instruccion PUSH.w o PUSH.b
                simulate_push_instruction(self, regnr, opcode)

            return addr

        elif As== 1:                                            # modo indexado
        #debo buscar lo que hay en la dirección + x lugares, que diga regnr, en memoria, y luego setearlo en regnr
            if opcstr == 0: # Instruccion RRC.w o RRC.b
                cy = None
                sumacontenidomemoria = None
                try:
                    sumacontenidomemoria = self.mem.mem_start + self.regs.get(regnr) + self.mem.load_word_at(addr)

                    if (sumacontenidomemoria >= 0xffc0): # estamos en la tabla de interrupciones
                        sumacontenidomemoria = self.regs.get(regnr) + self.mem.load_word_at(addr)

                    contenido_memoria = self.mem.load_word_at(sumacontenidomemoria)

                    self.regs.set(regnr, contenido_memoria)

                    simulate_rrc_instruction(self, regnr, opcode)
                except MemoryException as ex:
                    if "Lectura de memoria no inicializada" in str(ex):
                        self.mem.store_word_at(sumacontenidomemoria, 0xabcd)
                        self.regs.set(regnr, self.mem.load_word_at(sumacontenidomemoria))

                        simulate_rrc_instruction(self, regnr, opcode)
                    elif "Direccion fuera de rango" in str(ex):
                        self.mem.store_word_at(self.mem.mem_start + self.regs.get(regnr) + self.mem.load_word_at(addr), 0xabcd)
                        self.regs.set(regnr, self.mem.load_word_at(self.mem.mem_start + self.regs.get(regnr) + self.mem.load_word_at(addr)))

                        simulate_rrc_instruction(self, regnr, opcode)

            elif opcstr == 2: # Instruccion RRA.w o RRA.b
                sumacontenidomemoria = None
                try:                
                    sumacontenidomemoria = self.mem.mem_start + self.regs.get(regnr) + self.mem.load_word_at(addr)

                    if (sumacontenidomemoria >= 0xffc0): # estamos en la tabla de interrupciones
                        sumacontenidomemoria = self.regs.get(regnr) + self.mem.load_word_at(addr)

                    contenido_memoria = self.mem.load_word_at(sumacontenidomemoria)

                    self.regs.set(regnr, contenido_memoria)

                    simulate_rra_instruction(self, regnr, opcode)
                except MemoryException as ex:
                    if "Lectura de memoria no inicializada" in str(ex):
                        self.mem.store_word_at(sumacontenidomemoria, 0xabcd)
                        self.regs.set(regnr, self.mem.load_word_at(sumacontenidomemoria))

                        simulate_rra_instruction(self, regnr, opcode)
                    elif "Direccion fuera de rango" in str(ex):
                        self.mem.store_word_at(self.mem.mem_start + self.regs.get(regnr) + self.mem.load_word_at(addr), 0xabcd)
                        self.regs.set(regnr, self.mem.load_word_at(self.mem.mem_start + self.regs.get(regnr) + self.mem.load_word_at(addr)))

                        simulate_rra_instruction(self, regnr, opcode)

            elif opcstr == 4: # Instruccion PUSH.w o PUSH.b
                sumacontenidomemoria = None
                try:
                    sumacontenidomemoria = self.mem.mem_start + self.regs.get(regnr) + self.mem.load_word_at(addr)

                    if (sumacontenidomemoria >= 0xffc0): # estamos en la tabla de interrupciones
                        sumacontenidomemoria = self.regs.get(regnr) + self.mem.load_word_at(addr)

                    contenido_memoria = self.mem.load_word_at(sumacontenidomemoria)

                    self.regs.set(regnr, contenido_memoria)

                    simulate_push_instruction(self, regnr, opcode)
                except MemoryException as ex:
                    if "Lectura de memoria no inicializada" in str(ex):
                        self.mem.store_word_at(sumacontenidomemoria, 0xabcd)
                        self.regs.set(regnr, self.mem.load_word_at(sumacontenidomemoria))

                        simulate_push_instruction(self, regnr, opcode)

                    elif "Direccion fuera de rango" in str(ex):
                        self.mem.store_word_at(self.mem.mem_start + self.regs.get(regnr) + self.mem.load_word_at(addr), 0xabcd)
                        self.regs.set(regnr, self.mem.load_word_at(self.mem.mem_start + self.regs.get(regnr) + self.mem.load_word_at(addr)))
                        
                        simulate_push_instruction(self, regnr, opcode)

            return addr+2
    
        elif As == 2:                                            # modo indirecto por registro
            if opcstr == 0: # Instruccion RRC.w o RRC.b

                try:
                    contenido_memoria = self.mem.load_word_at(self.regs.get(regnr))

                    self.regs.set(regnr, contenido_memoria)

                    simulate_rrc_instruction(self, regnr, opcode)
                except MemoryException as ex:
                    if "Lectura de memoria no inicializada" in str(ex):
                        self.mem.store_word_at(self.regs.get(regnr), 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(self.regs.get(regnr)))

                        simulate_rrc_instruction(self, regnr, opcode)
                    elif "Direccion fuera de rango" in str(ex):
                        self.mem.store_word_at(self.mem.mem_start + self.regs.get(regnr), 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(self.mem.mem_start + self.regs.get(regnr)))

                        simulate_rrc_instruction(self, regnr, opcode)

            elif opcstr == 2: # Instruccion RRA.w o RRA.b

                try:
                    contenido_memoria = self.mem.load_word_at(self.regs.get(regnr))

                    self.regs.set(regnr, contenido_memoria)

                    simulate_rra_instruction(self, regnr, opcode)
                except MemoryException as ex:
                    if "Lectura de memoria no inicializada" in str(ex):
                        self.mem.store_word_at(self.regs.get(regnr), 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(self.regs.get(regnr)))
                        
                        simulate_rra_instruction(self, regnr, opcode)
                    elif "Direccion fuera de rango" in str(ex):
                        self.mem.store_word_at(self.mem.mem_start + self.regs.get(regnr), 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(self.mem.mem_start + self.regs.get(regnr)))
                        
                        simulate_rra_instruction(self, regnr, opcode)

            elif opcstr == 4: # Instruccion PUSH.w o PUSH.b

                try:
                    contenido_memoria = self.mem.load_word_at(self.regs.get(regnr))

                    print(self.mem.dump(self.regs.get(regnr), 32))

                    self.regs.set(regnr, contenido_memoria)

                    simulate_push_instruction(self, regnr, opcode)
                except MemoryException as ex:
                    if "Lectura de memoria no inicializada" in str(ex):
                        self.mem.store_word_at(self.regs.get(regnr), 0xABCD)

                        print(self.mem.dump(self.regs.get(regnr), 32))

                        self.regs.set(regnr, self.mem.load_word_at(self.regs.get(regnr)))

                        simulate_push_instruction(self, regnr, opcode)
                    elif "Direccion fuera de rango" in str(ex):
                        self.mem.store_word_at(self.mem.mem_start + self.regs.get(regnr), 0xABCD)

                        print(self.mem.dump(self.mem.mem_start + self.regs.get(regnr), 32))

                        self.regs.set(regnr, self.mem.load_word_at(self.mem.mem_start + self.regs.get(regnr)))

                        simulate_push_instruction(self, regnr, opcode)
            
            if self.mem.load_byte_at(addr) != None:
                return addr

        elif As== 3:                                            # modo indirecto autoincrementado

            if opcstr == 0: # Instruccion RRC.w o RRC.b

                try:
                    contenido_memoria = self.mem.load_word_at(self.regs.get(regnr))

                    self.regs.set(regnr, contenido_memoria)

                    simulate_rrc_instruction(self, regnr, opcode)
                except MemoryException as ex:
                    if "Lectura de memoria no inicializada" in str(ex):
                        self.mem.store_word_at(self.regs.get(regnr), 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(self.regs.get(regnr)))

                        simulate_rrc_instruction(self, regnr, opcode)
                    elif "Direccion fuera de rango" in str(ex):
                        self.mem.store_word_at(self.mem.mem_start + self.regs.get(regnr), 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(self.mem.mem_start + self.regs.get(regnr)))

                        simulate_rrc_instruction(self, regnr, opcode)
                finally:
                    if self.opc_Byte(opcode):
                        self.regs.set(regnr, self.regs.get(regnr) + 0x0001)
                    else:
                        self.regs.set(regnr, self.regs.get(regnr) + 0x0002)

            elif opcstr == 2: # Instruccion RRA.w o RRA.b

                try:
                    contenido_memoria = self.mem.load_word_at(self.regs.get(regnr))

                    self.regs.set(regnr, contenido_memoria)

                    simulate_rra_instruction(self, regnr, opcode)
                except MemoryException as ex:
                    if "Lectura de memoria no inicializada" in str(ex):
                        self.mem.store_word_at(self.regs.get(regnr), 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(self.regs.get(regnr)))

                        simulate_rra_instruction(self, regnr, opcode)
                    elif "Direccion fuera de rango" in str(ex):
                        self.mem.store_word_at(self.mem.mem_start + self.regs.get(regnr), 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(self.mem.mem_start + self.regs.get(regnr)))

                        simulate_rra_instruction(self, regnr, opcode)
                finally:
                    if self.opc_Byte(opcode):
                        self.regs.set(regnr, self.regs.get(regnr) + 0x0001)
                    else:
                        self.regs.set(regnr, self.regs.get(regnr) + 0x0002)

            elif opcstr == 4: # Instruccion PUSH.w o PUSH.b

                try:
                    contenido_memoria = self.mem.load_word_at(self.regs.get(regnr))

                    self.regs.set(regnr, contenido_memoria)

                    simulate_push_instruction(self, regnr, opcode)
                except MemoryException as ex:
                    if "Lectura de memoria no inicializada" in str(ex):
                        self.mem.store_word_at(self.regs.get(regnr), 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(self.regs.get(regnr)))

                        simulate_push_instruction(self, regnr, opcode)
                    elif "Direccion fuera de rango" in str(ex):
                        self.mem.store_word_at(self.mem.mem_start + self.regs.get(regnr), 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(self.mem.mem_start + self.regs.get(regnr)))

                        simulate_push_instruction(self, regnr, opcode)
                finally:
                    if self.opc_Byte(opcode):
                        self.regs.set(regnr, self.regs.get(regnr) + 0x0001)
                    else:
                        self.regs.set(regnr, self.regs.get(regnr) + 0x0002)

            if self.mem.load_byte_at(addr) != None:
                return addr



    def opd_single_type2(self, addr, opcode, opcstr):
        """ Desensamblar instruccion SWPB, SXT, CALL """
        As = self.opc_As(opcode)

        # Abreviamos el numero de registro
        regnr = self.opc_register(opcode)

        # Acordarse del estado del CY en ST
        cy = self.regs.get_SR('C')

        if As == 0:                                             # modo por registro

            if opcstr == 1:     # INSTRUCCION SWPB
                simulate_swpb_instruction(self, regnr)
            elif opcstr == 3:   # INSTRUCCION SXT
                simulate_sxt_instruction(self, regnr, True)
            elif opcstr == 5:   # INSTRUCCION CALL
                simulate_call_instruction(self, regnr)
                return self.regs.get(0)

            return addr
        elif As == 1:                                           # modo indexado
            if opcstr == 1: # INSTRUCCION SWPB                
                sumacontenidomemoria = None
                try:
                    sumacontenidomemoria = self.mem.mem_start + self.regs.get(regnr) + self.mem.load_word_at(addr)

                    if (sumacontenidomemoria >= 0xffc0): # estamos en la tabla de interrupciones
                        sumacontenidomemoria = self.regs.get(regnr) + self.mem.load_word_at(addr)

                    contenido_memoria = self.mem.load_word_at(sumacontenidomemoria)

                    self.regs.set(regnr, contenido_memoria)

                    simulate_swpb_instruction(self, regnr)
                except MemoryException as ex:
                    if "Lectura de memoria no inicializada" in str(ex):
                        self.mem.store_word_at(sumacontenidomemoria, 0xabcd)
                        self.regs.set(regnr, self.mem.load_word_at(sumacontenidomemoria))

                        simulate_swpb_instruction(self, regnr)        
                    elif "Direccion fuera de rango" in str(ex):
                        self.mem.store_word_at(self.mem.mem_start + self.regs.get(regnr) + self.mem.load_word_at(addr), 0xabcd)
                        self.regs.set(regnr, self.mem.load_word_at(self.mem.mem_start + self.regs.get(regnr) + self.mem.load_word_at(addr)))

                        simulate_swpb_instruction(self, regnr)

            elif opcstr == 3: # INSTRUCCION SXT
                sumacontenidomemoria = None
                try:
                    sumacontenidomemoria = self.mem.mem_start + self.regs.get(regnr) + self.mem.load_word_at(addr)

                    if (sumacontenidomemoria >= 0xffc0): # estamos en la tabla de interrupciones
                        sumacontenidomemoria = self.regs.get(regnr) + self.mem.load_word_at(addr)

                    contenido_memoria = self.mem.load_word_at(sumacontenidomemoria)

                    self.regs.set(regnr, contenido_memoria)

                    simulate_sxt_instruction(self, regnr)
                except MemoryException as ex:
                    if "Lectura de memoria no inicializada" in str(ex):
                        self.mem.store_word_at(sumacontenidomemoria, 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(sumacontenidomemoria))

                        simulate_sxt_instruction(self, regnr)
                    elif "Direccion fuera de rango" in str(ex):
                        self.mem.store_word_at(self.mem.mem_start + self.regs.get(regnr) + self.mem.load_word_at(addr), 0xabcd)
                        self.regs.set(regnr, self.mem.load_word_at(self.mem.mem_start + self.regs.get(regnr) + self.mem.load_word_at(addr)))

                        simulate_sxt_instruction(self, regnr)
            
            elif opcstr == 5: # INSTRUCCION CALL
                sumacontenidomemoria = None
                try:
                    sumacontenidomemoria = self.mem.mem_start + self.regs.get(regnr) + self.mem.load_word_at(addr)

                    if (sumacontenidomemoria >= 0xffc0): # estamos en la tabla de interrupciones
                        sumacontenidomemoria = self.regs.get(regnr) + self.mem.load_word_at(addr)

                    contenido_memoria = self.mem.load_word_at(sumacontenidomemoria)

                    self.regs.set(regnr, contenido_memoria)

                    simulate_call_instruction(self, regnr)

                    return self.regs.get(0)

                except MemoryException as ex:
                    if "Lectura de memoria no inicializada" in str(ex):
                        self.mem.store_word_at(sumacontenidomemoria, 0xabcd)

                        self.regs.set(regnr, self.mem.load_word_at(sumacontenidomemoria))

                        simulate_call_instruction(self, regnr)

                        return self.regs.get(0)

                    elif "Direccion fuera de rango" in str(ex):                    
                        self.mem.store_word_at(self.mem.mem_start + self.regs.get(regnr) + self.mem.load_word_at(addr), 0xabcd)
                        self.regs.set(regnr, self.mem.load_word_at(self.mem.mem_start + self.regs.get(regnr) + self.mem.load_word_at(addr)))

                        simulate_call_instruction(self, regnr)

                        return self.regs.get(0)

            return addr+2
        elif As == 2:                                           # modo indirecto por registro

            if opcstr == 1: # INSTRUCCION SWPB

                try:
                    contenido_memoria = self.mem.load_word_at(self.regs.get(regnr))

                    self.regs.set(regnr, contenido_memoria)

                    simulate_swpb_instruction(self, regnr)
                except MemoryException as ex:
                    if "Lectura de memoria no inicializada" in str(ex):
                        self.mem.store_word_at(self.regs.get(regnr), 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(self.regs.get(regnr)))

                        simulate_swpb_instruction(self, regnr)
                    elif "Direccion fuera de rango" in str(ex):
                        self.mem.store_word_at(self.mem.mem_start + self.regs.get(regnr), 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(self.mem.mem_start + self.regs.get(regnr)))

                        simulate_swpb_instruction(self, regnr)

            elif opcstr == 3: # INSTRUCCION SXT

                try:
                    contenido_memoria = self.mem.load_word_at(self.regs.get(regnr))

                    self.regs.set(regnr, contenido_memoria)

                    simulate_sxt_instruction(self, regnr)
                except MemoryException as ex:
                    if "Lectura de memoria no inicializada" in str(ex):
                        self.mem.store_word_at(self.regs.get(regnr), 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(self.regs.get(regnr)))

                        simulate_sxt_instruction(self, regnr)
                    elif "Direccion fuera de rango" in str(ex):
                        self.mem.store_word_at(self.mem.mem_start + self.regs.get(regnr), 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(self.mem.mem_start + self.regs.get(regnr)))

                        simulate_sxt_instruction(self, regnr)

            elif opcstr == 5: # INSTRUCCION CALL

                try:
                    contenido_memoria = self.mem.load_word_at(self.regs.get(regnr))

                    print(self.mem.dump(self.regs.get(regnr), 32))

                    self.regs.set(regnr, contenido_memoria)

                    simulate_call_instruction(self, regnr)
  
                    return self.regs.get(0)

                except MemoryException as ex:
                    if "Lectura de memoria no inicializada" in str(ex):
                        self.mem.store_word_at(self.regs.get(regnr), 0xABCD)

                        print(self.mem.dump(self.regs.get(regnr), 32))

                        self.regs.set(regnr, self.mem.load_word_at(self.regs.get(regnr)))

                        simulate_call_instruction(self, regnr)

                        return self.regs.get(0)

                    elif "Direccion fuera de rango" in str(ex):
                        self.mem.store_word_at(self.mem.mem_start + self.regs.get(regnr), 0xABCD)

                        print(self.mem.dump(self.mem.mem_start + self.regs.get(regnr), 32))

                        self.regs.set(regnr, self.mem.load_word_at(self.mem.mem_start + self.regs.get(regnr)))

                        simulate_call_instruction(self, regnr)

                        return self.regs.get(0)

            return addr
        elif As == 3:                                           # modo indirecto autoincrementado

            if opcstr == 1: # INSTRUCCION SWPB

                try:                    
                    contenido_memoria = self.mem.load_word_at(self.regs.get(regnr))

                    self.regs.set(regnr, contenido_memoria)

                    simulate_swpb_instruction(self, regnr)
                except MemoryException as ex:
                    if "Lectura de memoria no inicializada" in str(ex):
                        self.mem.store_word_at(self.regs.get(regnr), 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(self.regs.get(regnr)))

                        simulate_swpb_instruction(self, regnr)                    
                    elif "Direccion fuera de rango" in str(ex):
                        self.mem.store_word_at(self.mem.mem_start + self.regs.get(regnr), 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(self.mem.mem_start + self.regs.get(regnr)))

                        simulate_swpb_instruction(self, regnr)
                finally:
                    self.regs.set(regnr, self.regs.get(regnr) + 0x0002)

            elif opcstr == 3: # INSTRUCCION SXT

                try:
                    contenido_memoria = self.mem.load_word_at(self.regs.get(regnr))

                    self.regs.set(regnr, contenido_memoria)

                    simulate_sxt_instruction(self, regnr)
                
                except MemoryException as ex:
                    if "Lectura de memoria no inicializada" in str(ex):
                        self.mem.store_word_at(self.regs.get(regnr), 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(self.regs.get(regnr)))

                        simulate_sxt_instruction(self, regnr)
                    
                    elif "Direccion fuera de rango" in str(ex):
                        self.mem.store_word_at(self.mem.mem_start + self.regs.get(regnr), 0xABCD)

                        self.regs.set(regnr, self.mem.load_word_at(self.mem.mem_start + self.regs.get(regnr)))

                        simulate_sxt_instruction(self, regnr)
                    
                finally:
                    self.regs.set(regnr, self.regs.get(regnr) + 0x0002)

            elif opcstr == 5: # INSTRUCCION CALL

                try:
                    contenido_memoria = self.mem.load_word_at(self.regs.get(regnr))

                    print(self.mem.dump(self.regs.get(regnr), 32))

                    self.regs.set(regnr, contenido_memoria)

                    simulate_call_instruction(self, regnr)
                    
                    return self.regs.get(0)

                except MemoryException as ex:
                    if "Lectura de memoria no inicializada" in str(ex):
                        self.mem.store_word_at(self.regs.get(regnr), 0xABCD)

                        print(self.mem.dump(self.regs.get(regnr), 32))

                        self.regs.set(regnr, self.mem.load_word_at(self.regs.get(regnr)))

                        simulate_call_instruction(self, regnr)
                        
                        return self.regs.get(0)

                    elif "Direccion fuera de rango" in str(ex):
                        self.mem.store_word_at(self.mem.mem_start + self.regs.get(regnr), 0xABCD)

                        print(self.mem.dump(self.mem.mem_start + self.regs.get(regnr), 32))

                        self.regs.set(regnr, self.mem.load_word_at(self.mem.mem_start + self.regs.get(regnr)))

                        simulate_call_instruction(self, regnr)
                        
                        return self.regs.get(0)

                finally:
                    self.regs.set(regnr, self.regs.get(regnr) + 0x0002)

            return addr



    def opd_single_reti(self, addr, opcode, opcstr):
        """ Desensamblar instruccion RETI """
        return "%-8s" % (opcstr)

    #
    #   Instrucciones de doble operando
    #

    def opd_double(self, addr, opcode, opcstr):
        pass
        """En grupos"""

    #
    #   Instrucciones de salto (condicional)
    #

    def opd_jump(self, addr, opcode, optype):
        """ Simular instrucciones de salto """

        offset = (opcode & 0x03ff) - 1    # salto se calcula desde la direccion
                                          # del opcode (addr ya fue incrementado!)
        if (offset & 0x0200) != 0:        # Positivo
            offset |= 0xfe00
        addr1 = (addr + 2*offset) & 0xffff

        if optype == self.JMP:
            return addr1

        elif optype == self.JNZ:
            return addr1 if not self.regs.get_SR('Z') else addr

        elif optype == self.JZ:
            return addr1 if self.regs.get_SR('Z') else addr

        elif optype == self.JC:
            return addr1 if self.regs.get_SR('C') else addr

        elif optype == self.JNC:
            return addr1 if not self.regs.get_SR('C') else addr

        elif optype == self.JN:
            return addr1 if self.regs.get_SR('N') else addr

        elif optype == self.JL:
            # La operacion != es el equivalente de una XOR
            if (self.regs.get_SR('N') != self.regs.get_SR('V')): return addr1
            else: return addr

        elif optype == self.JGE:
            # La operacion != es el equivalente de una XOR
            if not (self.regs.get_SR('N') != self.regs.get_SR('V')): return addr1
            else: return addr


    def disassemble(self, start, end):
        """ Desensamblar el bloque de memoria de <start> a <end>
        """
        pc = start
        while pc <= end:
            new_pc, s = self.one_opcode(pc)
            print("{:04x}  {:s}".format(pc, s))
            pc = new_pc


    def disassemble_all(self, handler):
        """ Desensamblar todos los lugares inicializados.
            El <handler> contiene la rutina que será llamada para hacer
            algo útil con <pc> y <s>  (<s> es el opcode desensamblado)
        """
        pc = self.mem.mem_start
        while pc < (self.mem.mem_start + self.mem.mem_size):
            if self.mem.load_word_at(pc) == None:
                pc += 2
                continue
            new_pc, s = self.one_opcode(pc)
            handler(pc, s)
            pc = new_pc


def main():
    from registers import Registers

    m = Memory(1024, mem_start = 0xfc00)
    r = Registers()
    s = Simulator(m, r)

    m.store_words_at(0xfd00, [
                0x3c55, 0x3e55,
                0x1005, 0x1015, 0x0019, 0x1026, 0x1037,
                0x1088, 0x1098, 0x001a, 0x10a9, 0x10b9,
                0x1105, 0x1196, 0x001b, 0x122b, 0x12bc,
                0x1300])

    m.store_word_at(0xfffe, 0xfd00)

    print(str(m))

    newpc = s.one_step(0xfffe)
    print("%04x" % newpc)

    newpc = s.one_step(newpc)
    print("%04x" % newpc)

    return 0

if __name__ == '__main__':
    main()