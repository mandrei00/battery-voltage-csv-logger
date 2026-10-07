import os
import csv
import time
from pathlib import Path
from datetime import datetime
import serial


# --- Настройки ---
PORT         = 'COM9'          # замените на ваш
BAUDRATE     = 115200
TIMEOUT      = 1               # сек, readline()
LOG_ROOT     = Path('log')
TAG          = 'voltage'
FLUSH_EVERY  = 10              # сбрасывать на диск каждые N строк
VOLTAGE_UNIT = 'V'             # единица измерения напряжения


def create_log_directory() -> Path:
    """Создаёт папку log/{время-старта}_{TAG}/ и возвращает её путь."""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_path = LOG_ROOT / f'{timestamp}_{TAG}'
    log_path.mkdir(parents=True, exist_ok=True)
    return log_path


def parse_voltage(line: str) -> float | None:
    """Извлекает число из строки, пришедшей с Arduino."""
    line = line.strip()
    if not line:
        return None

    # Если Arduino шлёт "VOLTAGE:1.234" — берём часть после двоеточия
    if ':' in line:
        line = line.split(':', 1)[1].strip()

    try:
        return float(line)
    except ValueError:
        return None


def main():
    log_path = create_log_directory()
    csv_file_path = log_path / 'data.csv'

    # Открываем файл в режиме потоковой записи
    with open(csv_file_path, mode='w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(['timestamp', f'voltage_{VOLTAGE_UNIT}'])
        csv_file.flush()
        os.fsync(csv_file.fileno())

        # Открываем последовательный порт
        ser = serial.Serial(PORT, BAUDRATE, timeout=TIMEOUT)

        rows_since_flush = 0

        print(f'Порт {PORT} открыт, скорость {BAUDRATE}')
        print(f'Запись в {csv_file_path}')
        print('Нажмите Ctrl+C для остановки...')

        try:
            while True:
                raw = ser.readline()

                if not raw:
                    # Таймаут — нет данных, продолжаем ждать
                    continue

                try:
                    line = raw.decode('utf-8', errors='ignore')
                except UnicodeDecodeError:
                    continue

                voltage = parse_voltage(line)
                if voltage is None:
                    continue

                # timestamp — абсолютное Unix-время в секундах (float)
                timestamp = time.time()
                print(f"{voltage=}")
                writer.writerow([f'{timestamp:.6f}', f'{voltage:.6f}'])
                rows_since_flush += 1

                # Периодический сброс на диск
                if rows_since_flush >= FLUSH_EVERY:
                    csv_file.flush()
                    os.fsync(csv_file.fileno())
                    rows_since_flush = 0

        except KeyboardInterrupt:
            print('\nОстановка записи...')

        finally:
            # Финальный сброс буфера
            csv_file.flush()
            os.fsync(csv_file.fileno())
            ser.close()
            print(f'Лог сохранён: {csv_file_path}')


if __name__ == '__main__':
    main()