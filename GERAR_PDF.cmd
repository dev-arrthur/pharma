@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0"
if errorlevel 1 exit /b 1
title Maximum - Relatorios da farmacia
set "pharmaOutput=%~dp0relatorios-gerados\Maximum-Farmacia-Relatorio.pdf"
set "pharmaHtml=%~dp0relatorios-gerados\Maximum-Farmacia-Relatorio.html"
set "pharmaExit=1"

:menu
cls
echo MAXIMUM - RELATORIOS DA FARMACIA
echo.
echo Escolha de onde o gerador deve ler as informacoes:
echo.
echo   1 - Consultar o MongoDB configurado no arquivo .env
echo   2 - Escolher um arquivo JSON, JSONL ou CSV
echo   3 - Escolher uma pasta com arquivos exportados
echo   0 - Sair
echo.
echo O programa usa os dados da origem escolhida; nao cria valores.
echo.
choice /c 1230 /n /m "Digite 1, 2, 3 ou 0: "
if errorlevel 4 goto canceled
if errorlevel 3 goto mode_folder
if errorlevel 2 goto mode_file
if errorlevel 1 goto mode_mongo
goto canceled

:mode_mongo
set "pharmaMode=mongo"
if not exist ".env" goto configure_env
goto prepare_python

:mode_file
set "pharmaMode=file"
goto prepare_python

:mode_folder
set "pharmaMode=folder"
goto prepare_python

:configure_env
if not exist ".env.example" goto missing_template
copy /b ".env.example" ".env" >nul
if errorlevel 1 goto env_error
echo.
echo Preencha MONGODB_URI e MONGODB_DB no arquivo que sera aberto.
echo Salve o arquivo e execute GERAR_PDF.cmd novamente.
echo Use um acesso de leitura ao banco original.
start "" /wait notepad.exe ".env"
set "pharmaExit=3"
goto done

:prepare_python
echo.
echo Preparando o gerador. Na primeira execucao, pode levar alguns minutos.
if not exist ".venv\Scripts\python.exe" goto find_python
".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 goto dependencies

:find_python
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto try_python
py -3 -m venv ".venv"
if errorlevel 1 goto venv_error
goto dependencies

:try_python
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto python_missing
python -m venv ".venv"
if errorlevel 1 goto venv_error

:dependencies
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "requirements.txt"
if errorlevel 1 goto install_error
echo.
echo Lendo os registros e preparando PDF e HTML...
if "%pharmaMode%"=="file" goto generate_file
if "%pharmaMode%"=="folder" goto generate_folder
".venv\Scripts\python.exe" "gerar_relatorio.py" "%pharmaOutput%"
set "pharmaExit=%errorlevel%"
goto check_result

:generate_file
".venv\Scripts\python.exe" "gerar_relatorio.py" "%pharmaOutput%" --escolher-arquivo
set "pharmaExit=%errorlevel%"
goto check_result

:generate_folder
".venv\Scripts\python.exe" "gerar_relatorio.py" "%pharmaOutput%" --escolher-pasta
set "pharmaExit=%errorlevel%"

:check_result
if "%pharmaExit%"=="0" goto generated
if "%pharmaExit%"=="2" goto partial
if "%pharmaExit%"=="3" goto canceled
echo.
echo O relatorio nao foi gerado. Confira a mensagem acima e tente novamente.
echo Nenhum PDF de uma execucao anterior sera aberto.
goto done

:partial
echo.
echo RELATORIO PARCIAL: a origem apresentou pendencias de leitura.
echo Confira as categorias e os avisos no inicio do relatorio.
goto open_outputs

:generated
echo.
echo Relatorios gerados com os registros da origem escolhida.

:open_outputs
if not exist "%pharmaOutput%" goto output_missing
if not exist "%pharmaHtml%" goto output_missing
start "" "%pharmaOutput%"
start "" "%pharmaHtml%"
echo.
echo Arquivos salvos na pasta relatorios-gerados.
goto done

:python_missing
echo.
echo Instale Python 3.10 ou superior para Windows e execute novamente.
echo Durante a instalacao, habilite a opcao Add Python to PATH.
goto fail

:venv_error
echo.
echo Nao foi possivel preparar o ambiente Python nesta pasta.
echo Extraia o ZIP em uma pasta onde voce tenha permissao de escrita.
goto fail

:install_error
echo.
echo Nao foi possivel instalar as dependencias. Confira a conexao com a internet.
goto fail

:missing_template
echo.
echo O arquivo .env.example nao foi encontrado. Baixe o projeto completo.
goto fail

:env_error
echo.
echo Nao foi possivel criar o arquivo .env nesta pasta.
goto fail

:output_missing
echo.
echo O gerador nao encontrou os dois arquivos de saida. Confira a mensagem acima.
goto fail

:canceled
echo.
echo Operacao cancelada. Nenhum relatorio foi aberto.
set "pharmaExit=3"
goto done

:fail
set "pharmaExit=1"

:done
echo.
pause
popd
exit /b %pharmaExit%
