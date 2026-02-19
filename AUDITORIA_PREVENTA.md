# Auditoría pre-venta — Inventory & Sales Manager

Fecha: 2026-02-19

## Veredicto ejecutivo

**Nivel actual del software: Intermedio-alto (7/10 técnico, 4/10 comercial).**

- A favor: arquitectura por capas clara, servicios separados, modelo transaccional y pruebas automáticas ya presentes.
- En contra: la suite actual de tests no está verde y hay inconsistencias funcionales en autenticación/permisos, por lo que **hoy no está listo para venderse como producto comercial**.

**Decisión:** no recomendar venta todavía. Recomendar una fase corta de hardening (2–4 semanas) antes de comercializar.

---

## Qué está bien (fortalezas)

1. **Arquitectura limpia y mantenible**
   - Separación explícita de dominio, servicios, repositorio e interfaz.
   - Inyección de dependencias desde el contenedor/aplicación.

2. **Persistencia y transacciones**
   - SQLite con `PRAGMA foreign_keys = ON`.
   - Migraciones versionadas (`schema_migrations`) y unit-of-work para operaciones críticas.

3. **Capas de negocio con reglas explícitas**
   - Validaciones de stock, precios y costos en servicios.
   - Manejo de errores de dominio específico (`ValidationError`, `AuthorizationError`, etc.).

4. **Cobertura funcional relevante para SMB**
   - Inventario, ventas, reposición, reporting, import/export Excel y tipo de cambio con fallback.

5. **Seguridad de PIN mejor que texto plano**
   - Hash PBKDF2 para PIN en repositorio.

---

## Bloqueadores para venta (prioridad crítica)

### 1) Estado de calidad: pruebas fallando

Se ejecutó la suite y hoy hay fallas activas:

- **21 tests totales: 14 pasan, 7 fallan**.
- Fallas concentradas en **autenticación/migraciones de usuarios** y **mensajes de permisos en reportes**.

Esto por sí solo bloquea salida comercial: vender con pruebas rojas aumenta riesgo de incidentes en producción.

### 2) Inconsistencia de credenciales admin por defecto

En migración se crea admin con PIN hash de `admin123`, mientras las pruebas y flujo esperado validan `admin123!`.
Resultado: falla login del admin inicial.

### 3) Contrato de errores/mensajes inestable

En reportes, al denegar permisos se emiten mensajes distintos a los esperados por tests. Esto sugiere contrato de UI/errores no estabilizado (especialmente importante si luego hay soporte técnico o manuales de uso).

### 4) Riesgo comercial por i18n/UX inconsistente

La app mezcla textos en inglés/español en UI y errores. Para venta formal (especialmente B2B) conviene unificar idioma y tono, o soportar i18n real.

---

## Nivel de producto (escala pre-venta)

- **Arquitectura y mantenibilidad:** 8/10
- **Calidad funcional actual:** 6/10
- **Seguridad práctica (PYME):** 6.5/10
- **UX/consistencia comercial:** 5/10
- **Operabilidad/soporte (logs, docs, runbook):** 6/10

**Nivel global recomendado:** **6.3/10** (no listo para vender, sí listo para endurecer y salir pronto).

---

## Plan de mejoras antes de vender (priorizado)

## Fase 0 — Bloqueadores (obligatorio, 2–5 días)

1. **Dejar suite en verde (100%)**
   - Corregir autenticación admin inicial y contrato de mensajes/errores.
   - Agregar regresiones para que no vuelva a romperse.

2. **Definir credenciales/primer acceso seguro**
   - Evitar credenciales predecibles en distribución.
   - Forzar cambio de PIN al primer inicio o asistente de bootstrap.

3. **Checklist de release mínimo**
   - `pytest` verde + smoke manual UI + export/import Excel básico.

## Fase 1 — Confiabilidad operativa (1 semana)

4. **Empaquetado y actualización**
   - Instalador firmado, versionado semántico, estrategia de upgrades de DB.

5. **Backups y recuperación**
   - Backup automático diario del `.db` + restauración guiada desde UI.

6. **Observabilidad real**
   - IDs de operación en logs, rotación configurable, logs de auditoría por usuario para acciones críticas.

## Fase 2 — Seguridad/compliance pyme (1 semana)

7. **Endurecer autenticación**
   - Política de PIN más fuerte, rate limit local para intentos fallidos, bloqueo temporal.

8. **Permisos por acción centralizados**
   - Matriz de permisos única (no checks dispersos).

9. **Protección de datos locales**
   - Cifrado de backup o carpeta de datos sensible (al menos opcional).

## Fase 3 — Producto vendible (1–2 semanas)

10. **UX comercial**
    - Unificar idioma, textos, estados vacíos, errores accionables y ayudas contextuales.

11. **Documentación para cliente final**
    - Manual de usuario, guía de instalación, FAQ de recuperación, política de soporte.

12. **QA de escenarios reales**
    - Casos con multi-operador, importes grandes, cortes de red (FX), cierres inesperados.

---

## Riesgos si se vende en estado actual

- Incidentes de login/admin al primer uso.
- Aumento de tickets por mensajes inconsistentes y UX no unificada.
- Riesgo reputacional por bugs detectables con tests automáticos.

---

## Recomendación final

**No vender todavía.**

Con una iteración corta de hardening (2–4 semanas), este proyecto puede pasar a un **nivel comercial inicial sólido (8/10)** para PYMEs, manteniendo el buen diseño que ya tiene y cerrando los huecos críticos detectados.
