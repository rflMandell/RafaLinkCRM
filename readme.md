<div align="center">

# RafaLink CRM

### Gestão comercial, relacionamento com clientes e organização do processo de vendas

**Centralize leads, contatos, empresas e oportunidades em uma experiência integrada de CRM.**

[Aplicação online](https://rafalinkfront.vercel.app/) · [Guia de desenvolvimento](docs/DESENVOLVIMENTO.md) · [Documentação da API](http://localhost:8000/docs)

</div>

---

## Visão geral

O **RafaLink CRM** é uma aplicação de Customer Relationship Management (CRM) desenvolvida para apoiar a organização de informações comerciais e o acompanhamento do relacionamento com clientes ao longo do processo de vendas.

O projeto reúne uma interface web, uma API em Python e persistência local em SQLite. Seu objetivo é oferecer uma base funcional para gerenciar o ciclo comercial, acompanhar atividades e consultar informações relevantes em um único ambiente.

Este repositório contém o frontend, o backend, scripts de inicialização e documentação técnica para executar e testar o sistema localmente.

## Funcionalidades

### Gestão comercial
- **Leads:** cadastro e acompanhamento de potenciais clientes, com suporte à conversão no fluxo comercial.
- **Empresas e contatos:** organização de dados de empresas e pessoas relacionadas.
- **Pipeline de vendas:** visualização e acompanhamento de oportunidades por etapas.
- **Atividades e agenda:** apoio ao planejamento e acompanhamento das interações comerciais.
- **Visão do cliente:** centralização de informações relevantes para consulta do relacionamento.

### Acompanhamento e produtividade
- **Campanhas e analytics:** recursos para organizar campanhas e consultar indicadores.
- **Forecast, metas e SLA:** funcionalidades de apoio ao acompanhamento de desempenho comercial.
- **Busca global:** localização de informações em diferentes áreas do CRM.
- **Importação CSV:** entrada de leads a partir de arquivos compatíveis.
- **Detecção de duplicados:** recursos para identificar registros potencialmente repetidos.
- **Automação, notificações e auditoria:** recursos para apoiar rotinas e rastrear atividades do sistema.
- **Permissões e múltiplas organizações:** controles de acesso por perfil e mecanismos de isolamento de dados entre organizações.
- **Recursos de IA demonstrativos:** funcionalidades simuladas para demonstrar possibilidades de apoio inteligente ao processo comercial.

> A disponibilidade e o comportamento de cada funcionalidade devem ser avaliados na versão atual do projeto. Os recursos de IA são descritos como simulados na documentação de desenvolvimento.

## Tecnologias

| Camada | Tecnologias |
|---|---|
| Interface | HTML, CSS e JavaScript |
| Backend / API | Python, FastAPI e Uvicorn |
| Banco de dados | SQLite |
| Testes | pytest |
| Execução local | Script Python de inicialização e ambiente virtual |
| API interativa | OpenAPI / Swagger UI, disponibilizada pelo FastAPI |

## Arquitetura do projeto

O projeto é organizado em componentes separados por responsabilidade:

```text
rafalinkfront/
├── backend/
│   ├── app/                  # API, persistência, rotas e regras de negócio
│   ├── tests/                # Testes automatizados
│   ├── data/                 # Banco local e arquivos de log gerados
│   ├── requirements.txt      # Dependências de execução
│   └── requirements-dev.txt  # Dependências de desenvolvimento/testes
├── frontend/                 # Páginas HTML, estilos CSS e JavaScript
├── docs/
│   └── DESENVOLVIMENTO.md    # Guia detalhado de desenvolvimento
├── scripts/                  # Scripts auxiliares e dados de demonstração
├── start.py                  # Preparação do ambiente e inicialização
└── README.md
```

### Fluxo de execução

1. O script `start.py` verifica a versão do Python e prepara um ambiente virtual quando necessário.
2. As dependências do backend são instaladas a partir dos arquivos de requisitos.
3. A API FastAPI é iniciada com Uvicorn.
4. A interface web é disponibilizada para acesso pelo navegador.
5. Os dados locais são persistidos em SQLite.

Por padrão, a aplicação local utiliza o endereço `http://localhost:8000`.

## Pré-requisitos

- **Python 3.10 ou superior**
- **Git**
- Conexão com a internet na primeira execução para instalar as dependências

Não é necessário instalar Node.js para executar o fluxo descrito no guia de desenvolvimento.

## Como executar localmente

### 1. Clone o repositório

```bash
git clone https://github.com/rflMandell/rafalinkfront.git
cd rafalinkfront
```

### 2. Inicie a aplicação

**Windows:**

```powershell
py start.py
```

**macOS / Linux:**

```bash
python3 start.py
```

Em ambientes nos quais `python` já aponta para o Python 3.10 ou superior, também é possível usar:

```bash
python start.py
```

Na primeira execução, o inicializador cria o ambiente virtual, instala as dependências e inicia o servidor. Em seguida, tenta abrir a tela de login no navegador.

Acesse:

- **Aplicação local:** http://localhost:8000/login.html
- **Documentação interativa da API:** http://localhost:8000/docs

Para encerrar o servidor, pressione `Ctrl+C` no terminal.

## Comandos úteis

O `start.py` centraliza as principais tarefas de execução e desenvolvimento.

| Comando | Descrição |
|---|---|
| `python start.py` | Prepara o ambiente e inicia a aplicação |
| `python start.py --dev` | Ativa o recarregamento do servidor durante o desenvolvimento |
| `python start.py --test` | Executa os testes automatizados |
| `python start.py --test -k permissoes` | Executa testes cujo nome corresponda ao filtro informado |
| `python start.py --demo` | Gera dados de demonstração |
| `python start.py --port 8001` | Inicia a aplicação em outra porta |
| `python start.py --no-browser` | Inicia sem abrir automaticamente o navegador |
| `python start.py --reset-db` | Solicita confirmação e reinicia o banco local |

No Windows, substitua `python` por `py` se esse for o comando configurado no ambiente. No macOS, pode ser necessário usar `python3`.

## Testes automatizados

Para executar a suíte de testes:

```bash
python start.py --test
```

Para filtrar testes por nome:

```bash
python start.py --test -k permissoes
```

Os testes são executados com pytest e, conforme o guia do projeto, utilizam uma cópia temporária do banco para evitar alterar o banco local de desenvolvimento.

A cobertura documentada inclui fluxos de autenticação e erros, leads, conversão, permissões, importação CSV, duplicados, isolamento entre organizações, busca e automação.

## Dados de demonstração

Para gerar dados de demonstração:

```bash
python start.py --demo
```

O projeto documenta contas de demonstração para explorar diferentes perfis de acesso:

| Perfil | E-mail | Senha |
|---|---|---|
| Administrador | `admin@rafalink.com` | `admin123` |
| Gerente comercial | `gerente@rafalink.com` | `gerente123` |
| Vendedor | `vendedor@rafalink.com` | `vendedor123` |
| Administrador de outra organização (teste de isolamento) | `admin@outraempresa.com` | `admin123` |

**Importante:** essas credenciais são destinadas exclusivamente à demonstração local. Não as utilize em ambientes expostos à internet nem em produção. Altere as senhas e configure os segredos de autenticação antes de qualquer implantação acessível por terceiros.

## API

A API é construída com FastAPI e oferece documentação interativa gerada a partir dos contratos das rotas.

Com o servidor local em execução, acesse:

```text
http://localhost:8000/docs
```

Para testar endpoints protegidos, autentique-se pelo endpoint de login da API e utilize o token de acesso no botão **Authorize** da documentação interativa.

O guia de desenvolvimento contém orientações adicionais sobre autenticação, formato de erros, testes e solução de problemas.

## Configuração e dados locais

- O banco SQLite é armazenado em `backend/data/rafalink.db`.
- Os logs locais são gravados em `backend/data/rafalink.log`.
- Os arquivos de dados gerados localmente não devem ser versionados.
- Para recomeçar a base local, use `python start.py --reset-db` e confirme a operação quando solicitado.

O comando de reinicialização pode apagar os dados locais do CRM. Faça uma cópia de segurança antes de utilizá-lo se houver informações que deseja preservar.

## Solução de problemas

**A porta 8000 já está em uso**

```bash
python start.py --port 8001
```

**O comando `python` não é reconhecido no Windows**

```powershell
py start.py
```

**A interface não consegue se comunicar com o servidor**

Verifique se o backend está em execução e se a aplicação está usando a porta correta. Para reiniciar o sistema, execute `python start.py`.

**Preciso consultar erros de execução**

Confira as mensagens exibidas no terminal e o arquivo de log local, quando gerado, em `backend/data/rafalink.log`.

## Segurança e ambiente de uso

O projeto possui recursos demonstrativos de autenticação, permissões e isolamento entre organizações, mas a configuração local não deve ser considerada automaticamente adequada para produção.

Antes de disponibilizar o sistema em uma rede ou ambiente público:

- Configure um valor forte e exclusivo para `JWT_SECRET`.
- Troque todas as credenciais de demonstração.
- Revise autenticação, autorização e isolamento entre organizações.
- Configure adequadamente o armazenamento de segredos e as variáveis de ambiente.
- Avalie HTTPS, política de CORS, logs, backups e tratamento de dados pessoais.
- Execute os testes e faça uma revisão de segurança da implantação.

## Documentação adicional

- [Guia de desenvolvimento](docs/DESENVOLVIMENTO.md)
- [Repositório no GitHub](https://github.com/rflMandell/rafalinkfront)
- [Aplicação online](https://rafalinkfront.vercel.app/)

## Status do projeto

O RafaLink CRM é um projeto em evolução. A estrutura atual permite explorar fluxos de CRM, executar a aplicação localmente e validar funcionalidades por meio de testes automatizados. Melhorias de produto, arquitetura, experiência de uso e segurança podem ser incorporadas de forma incremental.

## Contribuição

Contribuições e sugestões são bem-vindas. Para propor uma melhoria:

1. Crie uma branch para sua alteração.
2. Faça mudanças pequenas e objetivas.
3. Execute os testes automatizados.
4. Descreva o objetivo da alteração e os passos para validá-la no pull request.

## Licença

Nenhuma licença foi identificada nesta documentação. Antes de reutilizar ou distribuir o projeto, verifique o arquivo de licença do repositório ou defina uma licença apropriada.
