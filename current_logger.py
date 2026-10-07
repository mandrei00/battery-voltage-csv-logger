import os
import csv
import time
from datetime import datetime
from ppk2_api.ppk2_api import PPK2_API

# Конфигурация
PORT = "COM11"
SAMPLE_RATE_HZ = 10
LOG_DIR = "log"
CURRENT_UNIT = "uA"  # PPK2 возвращает значения тока в микроампер

def create_log_directory():
    """Создаёт папку log/{время-старта}_current/ и возвращает её путь."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = os.path.join(LOG_DIR, f"{timestamp}_current")
    os.makedirs(log_path, exist_ok=True)
    return log_path

def main():
    # Создаём директорию для логов
    log_path = create_log_directory()
    csv_file_path = os.path.join(log_path, "data.csv")

    # Открываем CSV-файл в режиме потоковой записи
    with open(csv_file_path, mode="w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        # Заголовок с указанием единицы измерения
        writer.writerow(["timestamp", f"current_{CURRENT_UNIT}"])
        csv_file.flush()
        os.fsync(csv_file.fileno())

        # Подключаемся к PPK2
        ppk2 = PPK2_API(PORT)

        # Инициализация (загрузка калибровки)
        ppk2.get_modifiers()

        # Переключаем в режим амперметра
        ppk2.use_ampere_meter()

        # Установка напряжения (требуется даже в режиме амперметра)
        ppk2.set_source_voltage(3300)

        # Запуск измерений
        ppk2.start_measuring()

        # Точка отсчёта для timestamp (монотонное время в секундах)
        start_time = time.monotonic()

        print(f"Запись в {csv_file_path} на частоте {SAMPLE_RATE_HZ} Гц")
        print("Нажмите Ctrl+C для остановки...")

        sample_interval = 1.0 / SAMPLE_RATE_HZ

        try:
            while True:
                loop_start = time.time()

                # Читаем данные с устройства
                read_data = ppk2.get_data()

                if read_data:
                    # get_samples может возвращать кортеж (samples, raw_digital)
                    result = ppk2.get_samples(read_data)

                    if isinstance(result, tuple):
                        samples = result[0]
                    else:
                        samples = result

                    if samples:
                        # Средний ток за период опроса (в мкА)
                        avg_current = sum(samples) / len(samples)

                        # timestamp — float секунд от начала записи
                        timestamp = time.monotonic() - start_time

                        # Записываем строку и сразу сбрасываем на диск
                        writer.writerow([f"{timestamp:.6f}", f"{avg_current:.3f}"])
                        csv_file.flush()
                        os.fsync(csv_file.fileno())

                # Поддерживаем частоту опроса
                elapsed = time.time() - loop_start
                sleep_time = sample_interval - elapsed

                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\nОстановка записи...")

        finally:
            ppk2.stop_measuring()
            print(f"Лог сохранён: {csv_file_path}")

if __name__ == "__main__":
    main()