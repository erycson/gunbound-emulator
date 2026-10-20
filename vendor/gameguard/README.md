# Arquivos fornecidos pelo operador

Copie aqui, fora do Git, a `ggauth50.dll` original e suas dependências aprovadas
(por exemplo, o CRT x86 da distribuição original), e `GunBoundServ3.exe` para
extração somente de leitura das constantes de transporte. Não renomeie uma DLL
de outra versão para passar por ggauth50. Não há download automático.

Hashes aceitos:

- ggauth50.dll: `a8d81e5276ac502cfa41ffd5142deeaaca102537409d141bf1e628c2daee5257`
- GunBoundServ3.exe: `7e954d735e380ddc757d1ab20bd4b9341b5bfb55ceb8a9c5dd60dbabb1052e57`

O executável original não é executado pelo adaptador. A DLL é executada somente
no helper Windows x86 isolado, com caminho absoluto, após conferência do hash.
O `.gitignore` desta pasta bloqueia todos os binários, inclusive DLLs auxiliares.
Não use `git add -f` para incluí-los.
