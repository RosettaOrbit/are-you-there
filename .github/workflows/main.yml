name: Vigilante

on:
  schedule:
    - cron: "*/5 * * * *"   # cada 5 minutos (GitHub a veces lo retrasa)
  workflow_dispatch:         # permite ejecutarlo a mano desde la pestaña Actions

concurrency:
  group: vigilante
  cancel-in-progress: false

jobs:
  revisar:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4

      - name: Recuperar estado anterior
        uses: actions/cache/restore@v4
        with:
          path: estado.json
          key: estado-${{ github.run_id }}
          restore-keys: estado-

      - name: Revisar Roblox y YouTube
        run: python3 vigilante_gh.py
        env:
          NTFY_TOPIC: ${{ secrets.NTFY_TOPIC }}
          ROBLOX_PLACE_IDS: ${{ secrets.ROBLOX_PLACE_IDS }}
          YOUTUBE_CHANNELS: ${{ secrets.YOUTUBE_CHANNELS }}

      - name: Guardar estado
        if: always()
        uses: actions/cache/save@v4
        with:
          path: estado.json
          key: estado-${{ github.run_id }}
