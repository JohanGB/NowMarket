# Declaración de uso de IA

- **Claude (Anthropic)** escribió el código, las pruebas y la documentación de las fases 0 a 3, el
  11-nov-2026, a partir de la ficha del proyecto que definió el autor.
- Los datos son oficiales y los descargó el autor con el script del proyecto (SIPSA del DANE, ONI de la
  NOAA); cada archivo está en `data/manifest.json` con su SHA-256. Claude leyó y verificó su estructura.
- Para los modelos se siguió un protocolo fijado antes de mirar la prueba (`config/modelos.yaml`). La
  prueba se corrió una sola vez y el código impide repetirla sin dejar constancia.
- Claude tomó, por delegación del autor, las decisiones de la fase 2 (D-018 a D-028 en `decisiones.md`).
- Verificación: 51 pruebas automáticas, revisión de cifras contra las celdas del Excel original y una
  revisión independiente del código por otro agente.
- El autor responde por el contenido. No es asesoría financiera.
