# Comparador de Padrones

Aplicación Python/PySide6 para filtrar padrones fiscales argentinos contra un master de clientes o proveedores.

## Windows

El paquete contiene `ComparadorPadrones.exe` y su carpeta `_internal`, que debe permanecer junto al ejecutable. La configuración está en `_internal/config.ini`.

Sin argumentos abre la interfaz gráfica. Con argumentos ejecuta el procesamiento sin abrir la GUI.

## SIRCIP: ejecución desatendida

En las propiedades de un acceso directo de Windows, campo **Destino**:

```text
"C:\ComparadorPadrones\ComparadorPadrones.exe" --auto SIRCIP "D:\Padrones\masterDataClientes.txt" "D:\Padrones\padronSIRCIP.txt" "D:\Padrones\SIRCIP_salida.prn"
```

En **Iniciar en**: `C:\ComparadorPadrones`.

Orden: `--auto SIRCIP MASTER PADRON SALIDA`. También se admite omitir `--auto` cuando se pasan todos los argumentos. Usar rutas absolutas y comillas si contienen espacios.

### Usar config.ini

```ini
[DEFAULT]
padron_auto = SIRCIP

[SIRCIP]
master_data = D:\Padrones\masterDataClientes.txt
padron = D:\Padrones\padronSIRCIP.txt
salida = D:\Padrones\SIRCIP_salida.prn
```

Ejecutar `ComparadorPadrones.exe --auto` o `ComparadorPadrones.exe --auto SIRCIP`.

### Formato SIRCIP

Entrada CSV: periodo, CUIT, razón social, certificado, CRC, letra de alícuota, hash. El filtro compara el segundo campo con el CUIT de la tercera columna del master separado por pipes. El resultado esperado conserva los registros coincidentes, incluida la letra y el hash, sin cabecera.

Ejemplo ficticio:

```text
202603,30100100106,Empresa de prueba,904,34,B,5225355222512555552512420
```

### RPA / PowerShell

```powershell
$p = Start-Process -FilePath 'C:\ComparadorPadrones\ComparadorPadrones.exe' -ArgumentList '--auto SIRCIP "D:\Padrones\masterDataClientes.txt" "D:\Padrones\padronSIRCIP.txt" "D:\Padrones\SIRCIP_salida.prn"' -Wait -PassThru
$p.ExitCode
```

Esperar la finalización antes de consumir el archivo. Código 0: éxito; 1: error controlado. Consultar comparador.log ante fallos.

## Desarrollo

```powershell
python -m pip install -r requirements.txt
python main.py --auto SIRCIP master.txt padron.txt salida.prn
python -m pip install pyinstaller
python -m PyInstaller --clean --noconfirm ComparadorPadrones.spec
```

## GitHub Actions

El workflow Windows genera un ZIP descargable desde Actions > ejecución > Artifacts. Extraer la carpeta completa antes de ejecutar. No incluye instalador Inno Setup.

No publicar masters reales, logs ni configuraciones empresariales en repositorios públicos.

### Windows Server 2016

Actions genera dos artefactos independientes:

- ComparadorPadrones-Windows: Python 3.13 / PySide6 6.11.1.
- ComparadorPadrones-Windows-Legacy: Python 3.11 / PySide6 6.5.3, candidato para Server 2016 (compatibilidad pendiente de prueba real).

Extraer el ZIP completo en una carpeta nueva; no mezclar DLL de ambas versiones. Ambas usan el mismo EXE y argumentos RPA. Conservar una copia de config.ini antes de actualizar.

Diagnóstico gráfico: ejecutar con `--check-gui` y consultar el código de salida y el log. Las pruebas CI se ejecutan en Windows moderno, no en Server 2016.
