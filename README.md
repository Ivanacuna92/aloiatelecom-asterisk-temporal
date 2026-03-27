# Plantillas de Configuración Asterisk

Esta carpeta contiene las configuraciones de Asterisk con placeholders genéricos para poder replicar en diferentes servidores.

## Placeholders utilizados

| Placeholder | Descripción |
|-------------|-------------|
| `__SERVER_PUBLIC_IP__` | IP pública del servidor Asterisk |
| `__TRUNK_IP__` | IP del proveedor SIP/trunk |
| `__TRUNK_NAME__` | Nombre del trunk |
| `__TRUNK_PREFIX__` | Prefijo requerido por el trunk |
| `__TRUNK_FROM_USER__` | Usuario/FROM del trunk |
| `__COUNTRY_CODE__` | Código de país (ej: 52 para México) |
| `__DOMAIN__` | Dominio para certificados SSL |

---

## Instrucciones para actualizar configs en un servidor

### 0. EXTRAER valores actuales (ANTES de hacer backup)

Los valores que necesitas probablemente ya están en tus configs actuales. Extráelos primero:

```bash
# Ver IP pública del servidor (external_media_address en pjsip)
grep -E "external_media_address|external_signaling_address" /etc/asterisk/pjsip_aloia.conf | head -1

# Ver IP del trunk
grep "match=" /etc/asterisk/pjsip_aloia.conf

# Ver nombre del trunk
grep -E "^\[.*\]$" /etc/asterisk/pjsip_aloia.conf | grep -v template | tail -5

# Ver from_user del trunk
grep "from_user=" /etc/asterisk/pjsip_aloia.conf

# Ver dominio de certificados
grep "dtls_cert_file" /etc/asterisk/pjsip_aloia.conf

# Ver prefijo en extensions
grep -E "TRUNK_PREFIX|219189|Prefijo" /etc/asterisk/extensions_aloia.conf | head -3
```

**Guarda estos valores, los necesitarás en el paso 3.**

### 1. BACKUP de configs locales

```bash
# Crear backup con fecha
sudo cp -r /etc/asterisk /etc/asterisk.backup.$(date +%Y%m%d_%H%M%S)

# Verificar que el backup existe
ls -la /etc/asterisk.backup.*
```

### 2. COPIAR plantillas del repo a /etc/asterisk

```bash
cd /var/www/TELECOM-BBVA

# Copiar las plantillas
sudo cp -r asterisk/* /etc/asterisk/

# Ajustar permisos
sudo chown -R asterisk:asterisk /etc/asterisk/
```

### 3. REEMPLAZAR placeholders con los valores extraídos en el paso 0

| Placeholder | Dónde encontrarlo en configs actuales |
|-------------|---------------------------------------|
| `__SERVER_PUBLIC_IP__` | `external_media_address` en pjsip_aloia.conf |
| `__TRUNK_IP__` | `match=` en pjsip_aloia.conf |
| `__TRUNK_NAME__` | Sección `[nombre]` del trunk en pjsip_aloia.conf |
| `__TRUNK_PREFIX__` | Comentarios en extensions_aloia.conf |
| `__TRUNK_FROM_USER__` | `from_user=` en pjsip_aloia.conf |
| `__COUNTRY_CODE__` | Generalmente `52` para México |
| `__DOMAIN__` | `dtls_cert_file` en pjsip_aloia.conf |

```bash
cd /etc/asterisk

# Reemplazar cada placeholder con TUS valores
sudo sed -i 's/__SERVER_PUBLIC_IP__/TU_IP_PUBLICA/g' *.conf
sudo sed -i 's/__TRUNK_IP__/IP_DEL_TRUNK/g' *.conf
sudo sed -i 's/__TRUNK_NAME__/nombre_trunk/g' *.conf
sudo sed -i 's/__TRUNK_PREFIX__/prefijo/g' *.conf
sudo sed -i 's/__TRUNK_FROM_USER__/from_user/g' *.conf
sudo sed -i 's/__COUNTRY_CODE__/52/g' *.conf
sudo sed -i 's/__DOMAIN__/tu.dominio.com/g' *.conf
```

### 4. VERIFICAR que no quedaron placeholders

```bash
grep -rn "__" /etc/asterisk/*.conf | grep -E "__[A-Z_]+__"
```

Si muestra resultados, hay placeholders pendientes de reemplazar.

### 5. RECARGAR Asterisk

```bash
sudo asterisk -rx "core reload"
sudo asterisk -rx "pjsip reload"
```

### 6. RESTAURAR si algo sale mal

```bash
sudo rm -rf /etc/asterisk
sudo mv /etc/asterisk.backup.FECHA /etc/asterisk
sudo asterisk -rx "core reload"
```

---

## Scripts AGI

Los scripts AGI se encuentran en `asterisk/agi-bin/` y deben copiarse a `/var/lib/asterisk/agi-bin/`:

```bash
# Copiar scripts AGI
sudo cp /var/www/TELECOM-BBVA/asterisk/agi-bin/*.py /var/lib/asterisk/agi-bin/

# Ajustar permisos
sudo chown asterisk:asterisk /var/lib/asterisk/agi-bin/*.py
sudo chmod +x /var/lib/asterisk/agi-bin/*.py
```

Scripts incluidos:
- `dialer_find_agent.py` - Busca agente disponible para marcador
- `find_available_agent.py` - Encuentra agente disponible en cola
- `mark_abandoned.py` - Marca llamada como abandonada
- `predictive_find_agent.py` - Busca agente para marcador predictivo
- `process_amd_result.py` - Procesa resultado de detección de contestadora
- `update_call_attempt.py` - Actualiza intento de llamada en BD
- `voicebot_process.py` - Procesamiento de voicebot

---

## Subir configs nuevas al repo (opcional)

Si este servidor tiene configs nuevas que deben ser plantilla para otros servidores:

```bash
cd /var/www/TELECOM-BBVA

# Copiar configs al repo
sudo cp -r /etc/asterisk/* asterisk/

# Reemplazar valores específicos por placeholders
cd asterisk
sed -i 's/TU_IP_PUBLICA/__SERVER_PUBLIC_IP__/g' *.conf
sed -i 's/IP_DEL_TRUNK/__TRUNK_IP__/g' *.conf
sed -i 's/nombre_trunk/__TRUNK_NAME__/g' *.conf
sed -i 's/prefijo/__TRUNK_PREFIX__/g' *.conf
sed -i 's/from_user/__TRUNK_FROM_USER__/g' *.conf
sed -i 's/tu.dominio.com/__DOMAIN__/g' *.conf

# Commit y push
git add -A
git commit -m "feat: Actualizar plantillas Asterisk desde [NOMBRE_SERVIDOR]"
git push
```
