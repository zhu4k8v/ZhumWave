# Как выпустить новую версию

1. Обновите номер версии в `version_info.txt`, `ZhumWave.spec` (если нужно)
   и `installer.nsi` (`APPVERSION`).
2. Соберите приложение:

   ```bat
   py -m pip install -r requirements.txt
   py make_icon.py
   py -m PyInstaller --noconfirm --clean ZhumWave.spec
   ```

3. Соберите установщик через NSIS:

   ```bat
   makensis installer.nsi
   ```

   Установщик появится в папке `release`.

4. Создайте портативный архив с `ZhumWave.exe`, `README.md` и `LICENSE.txt`.
5. Посчитайте SHA-256 для установщика и архива и обновите `SHA256SUMS.txt`.
6. На GitHub откройте **Releases → Draft a new release**:
   - tag: `v1.0.0`;
   - заголовок: `ZhumWave 1.0.0`;
   - прикрепите установщик, портативный архив и `SHA256SUMS.txt`;
   - опубликуйте релиз.

Не коммитьте EXE, ZIP и папку `release` в Git — они предназначены для раздела
Releases.
