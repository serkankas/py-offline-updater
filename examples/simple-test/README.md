# Simple Engine Test

Update engine'in temel 3 fonksiyonunu test eden basit paket.

**Son Test:** 2026-01-28 - ByteDevKit (imx93) - ✅ PASSED

## Test Edilen Action'lar

| # | Action | Açıklama | Durum |
|---|--------|----------|-------|
| 1 | `file_copy` | Python dosyası `/tmp/update_test/` altına kopyalanır | ✅ |
| 2 | `command` | Kopyalanan Python scripti çalıştırılır | ✅ |
| 3 | `file_sync` | `scripts/` dizini mirror modda senkronize edilir | ✅ |

## Beklenen Çıktılar

Update tamamlandıktan sonra `/tmp/update_test/` altında:

```
/tmp/update_test/
├── test_script.py      # file_copy ile kopyalandı
├── test_output.txt     # command ile oluşturuldu (script çıktısı)
└── scripts/            # file_sync ile senkronize edildi
    ├── config.txt
    └── helper.sh
```

## Paketi Oluşturma ve Test Etme

```bash
# 1. Paketi oluştur
cd examples/simple-test
tar -czvf ../../simple-test.tar.gz manifest.yml files/

# 2. Web UI üzerinden yükle
# http://CIHAZ_IP:8123 adresine git
# simple-test.tar.gz dosyasını yükle
# "Apply Update" butonuna bas

# 3. Sonuçları kontrol et (cihazda)
cat /tmp/update_test/test_output.txt
ls -la /tmp/update_test/scripts/
```

## Başarı Kriterleri

- [x] `test_script.py` kopyalanmış olmalı
- [x] `test_output.txt` oluşturulmuş olmalı (script çalıştı)
- [x] `scripts/` dizini içinde `config.txt` ve `helper.sh` olmalı

## Test Sonuçları (2026-01-28)

**Cihaz:** ByteDevKit (imx93)
**Update Service:** /opt/updater/

```
Starting update: simple-test.tar.gz
Extracting package to /opt/updater/tmp/a5039be7-e995-4ff6-9768-020f4e3f75df
Package extracted successfully
Update completed successfully
```

**Doğrulama:**
```bash
root@bytedevkit-imx93:~# cat /tmp/update_test/test_output.txt
==================================================
UPDATE ENGINE TEST RESULTS
==================================================
[OK] file_copy: Python dosyasi basariyla kopyalandi
[OK] command: Python scripti basariyla calistirildi
==================================================

root@bytedevkit-imx93:~# ls -la /tmp/update_test/scripts/
config.txt   helper.sh
```

**Sonuç:** 3/3 test başarılı ✅
