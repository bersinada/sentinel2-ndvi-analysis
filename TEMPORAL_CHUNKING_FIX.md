# Aylık Temporal Chunking Optimizasyonu

## Problem
- CDSE STAC API'sı 180 günü aşan tarih aralıklarında hata veriyor
- 180 günlük chunks kullanıldığında dahi tek aydaki veriler getiriliyor
- Daha iyi sonuçlar için **aylık aramaların** yapılması gerekiyor

## Çözüm
`core/downloader.py` aylık chunking sistemi ile güncellendi.

### 1. **Aylık Chunking Fonksiyonu**
```python
def split_date_range_into_monthly_chunks(
    start_date: datetime, end_date: datetime
) -> list[tuple[datetime, datetime]]:
```

- Verilen tarih aralığını **takvim aylarına** böler
- Her ayı tam ay başından (1. gün) ay sonuna (31. gün vs.) kadar kapsar
- Başlangıç ve bitiş tarihlerine göre dinamik olarak ayarlanır

**Örnek:**
```
Giriş:  2023-01-15 / 2023-03-20
Çıkış:  [(2023-01-01, 2023-01-31),
         (2023-02-01, 2023-02-28),
         (2023-03-01, 2023-03-20)]  ← son ay kullanıcı tarihiyle sınırlandı
```

```
Giriş:  2023-01-01 / 2024-12-31 (2 yıl)
Çıkış:  24 aylık chunk
```

### 2. **search_scenes() Metodu**
- Config'teki tarih aralığını parse eder
- **Aylık chunks için** STAC katalog sorguları yapılır
- Her ay için ayrı arama yapılır → daha fazla sonuç
- Duplicateler filtrelenir

### 3. **Avantajları**
✅ **Daha iyi sonuçlar:** Ay-bazlı aramayla daha fazla sahne bulunur  
✅ **API uyumlu:** 180 günlük limit problemini tamamen çözer  
✅ **Mantıksal:** Günlük veriler ay bazında organize  
✅ **Otomatik:** Manuel ayarlama gerekmez  

---

## Kullanım

Hiçbir şey değişmemiş—kod otomatik olarak aylık chunks oluşturur:

```yaml
search_date_range: "2023-01-01/2024-12-31"  # 24 aylık chunk
```

### Logging Çıktısı Örneği

```
INFO: Split date range into 24 monthly chunks
INFO: Processing chunk 1/24: 2023-01-01 to 2023-01-31
INFO: Processing chunk 2/24: 2023-02-01 to 2023-02-28
INFO: Processing chunk 3/24: 2023-03-01 to 2023-03-31
...
INFO: Processing chunk 24/24: 2024-12-01 to 2024-12-31
INFO: Found 180 clean scenes across all chunks
```

---

## Teknik Detaylar

### Takvim Mantığı
- **Başlangıç:** Verilen tarihten önceki ayın 1. gününe ayarlanır
- **Bitiş:** Her ayın son günü (Şubat'ta 28/29 gün, vs.)
- **Son Ay:** Kullanıcı bitiş tarihine kadar sınırlandırılır

### Duplicate Avoidance
```python
if not any(s["id"] == item.id for s in clean):
    clean.append(...)
```
Overlap bölgelerinde aynı sahne iki kez eklenmez.

### Error Handling
```python
except Exception as exc:
    logger.error("Search failed for chunk %d (%s to %s): %s", 
                chunk_idx, chunk_start.date(), chunk_end.date(), exc)
    raise
```
Her chunk başarısızlığında detaylı hata logu.

---

## İstatistikler

| Senaryolar | Chunk Sayısı | Sonuç |
|---|---|---|
| 1 ay (2023-01) | 1 | Tam ay aranır |
| 6 ay (2023-01 to 2023-06) | 6 | 6 ayrı sorgu |
| 1 yıl (2023-01 to 2023-12) | 12 | 12 ayrı sorgu |
| 2 yıl (2023-01 to 2024-12) | 24 | 24 ayrı sorgu |

---

## Geçmiş Not

Önceki **180 günlük chunking** sistemi kaldırıldı. Aylık system daha iyi performans sunuyor.

---

## Test Etme

Uzun bir tarih aralığı ile test et:

```yaml
search_date_range: "2022-01-01/2024-12-31"  # 3 yıl = 36 ayık chunk
cloud_threshold: 20
max_items: 100
```

Çıktı:
```
INFO: Split date range into 36 monthly chunks
... (36 chunk işlenecek)
INFO: Found X clean scenes across all chunks
```

