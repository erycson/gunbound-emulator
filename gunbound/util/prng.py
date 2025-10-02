
class PRNGGenerator:
    """
    Replica o gerador de números pseudoaleatórios do servidor,
    que usa duas iterações de um PRNG Park-Miller (rand0).
    """
    def __init__(self, seed1: int, seed2: int = 0, seed3: int = 7):
        """
        Inicializa o gerador com os valores seed2 e seed3.
        Estes valores são usados para inicializar o estado interno.
        Args:
            seed2 (int): Valor inicial para o estado em offset +4. Ainda não descoberto a origem e se é estático.
            seed3 (int): Valor inicial para o estado em offset +C. Ainda não descoberto a origem e se é estático.
        """
        # A "seed" é um estado interno com 3 partes, como visto no Assembly
        self.state = {
            'seed_ptr_0': seed1,
            'seed_ptr_4': seed2, # Este é o valor gerado e realimentado
            'seed_ptr_c': seed3
        }

    def _park_miller_step(self):
        """
        Replica a função sub_449C10.
        Este é um gerador Park-Miller (também conhecido como Lehmer RNG ou rand0).
        Fórmula: seed = (seed * a) mod m
        """
        IA = 16807
        IM = 2147483647 # (2^31 - 1)
        IQ = 127773
        IR = 2836

        # Lê a seed atual
        seed = self.state['seed_ptr_0']
        
        # O Assembly faz uma divisão complexa para evitar overflow,
        # que é matematicamente equivalente a isto:
        k = seed // IQ
        seed = IA * (seed - k * IQ) - IR * k
        
        if seed < 0:
            seed += IM
        
        # Atualiza o estado (a nova seed)
        self.state['seed_ptr_0'] = seed
        
        return seed

    def generate_value(self) -> int:
        """
        Replica a função Server_PRNGGenerator, que chama _park_miller_step duas vezes.
        """
        val1 = self._park_miller_step()
        val2 = self._park_miller_step()
        
        # xor esi, eax
        result = val1 ^ val2
        
        # and esi, 0FFF0FFFFh
        result &= 0xFFF0FFFF
        
        # mov eax, [edi+0Ch]
        # shl eax, 18h
        # or esi, eax
        high_bits = self.state['seed_ptr_c'] << 24
        result |= high_bits
        
        # mov [edi+4], esi
        self.state['seed_ptr_4'] = result
        
        # mov dword ptr [edi+8], 0
        # A função zera o valor no offset +8, mas o propósito não é claro até agora,
        # por isso, por hora é ignorado.
        
        return result
