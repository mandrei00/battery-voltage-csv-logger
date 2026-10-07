import serial
import csv
import time
from pathlib import Path
from datetime import datetime
from threading import Thread, Event
from queue import Queue, Empty

# --- Настройки ---
PORT       = 'COM9'           # замените на ваш
BAUDRATE   = 115200
TIMEOUT    = 1                # сек, readline()
LOG_ROOT   = Path('log')
TAG        = 'voltage'
FLUSH_EVERY = 10              # сбрасывать на диск каждые N строк

def make_log_dir():
    """Создаёт log/<YYYY-MM-DD_HH-MM-SS>_voltage/ и возвращает путь."""
    LOG_ROOT.mkdir(exist_ok=True)
    stamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    d = LOG_ROOT / f'{stamp}_{TAG}'
    d.mkdir()
    return d

def reader_thread(ser, q: Queue, stop: Event):
    """Читает Serial и кладёт (timestamp, voltage) в очередь."""
    while not stop.is_set():
        try:
            raw = ser.readline()
        except serial.SerialException as e:
            q.put(('__ERROR__', f'SerialException: {e}'))
            break

        if not raw:
            continue  # таймаут, просто ждём

        line = raw.decode('ascii', errors='ignore').strip()
        if not line:
            continue

        # Пропускаем баннер "CR1632 Battery Logger"
        try:
            voltage = float(line)
        except ValueError:
            q.put(('__SKIP__', line))
            continue

        # timestamp ставится здесь — максимально близко к моменту приёма
        q.put((time.time(), voltage))

    q.put(('__EOF__', None))

def writer_thread(q: Queue, stop: Event, csv_path: Path, err_path: Path):
    """Пишет данные из очереди в CSV."""
    n = 0
    with open(csv_path, 'w', newline='') as f, \
         open(err_path, 'a') as fe:

        w = csv.writer(f)
        w.writerow(['timestamp', 'voltage'])
        f.flush()

        while not stop.is_set() or not q.empty():
            try:
                item = q.get(timeout=0.5)
            except Empty:
                continue

            kind, payload = item

            if kind == '__EOF__':
                break
            elif kind == '__SKIP__':
                fe.write(f'{datetime.now().isoformat()} SKIP: {payload!r}\n')
                fe.flush()
                continue
            elif kind == '__ERROR__':
                fe.write(f'{datetime.now().isoformat()} ERROR: {payload}\n')
                fe.flush()
                break

            ts, v = kind, payload
            # ts — Unix time (float, секунды с долями)
            w.writerow([f'{ts:.3f}', f'{v:.5f}'])
            n += 1

            if n % FLUSH_EVERY == 0:
                f.flush()

            if n % 100 == 0:
                print(f'{n} строк записано', end='\r')

        f.flush()

    print(f'\nИтого: {n} строк → {csv_path}')

def main():
    log_dir = make_log_dir()
    csv_path = log_dir / 'data.csv'
    err_path = log_dir / 'errors.log'
    print(f'Лог: {csv_path}')

    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=TIMEOUT)
    except serial.SerialException as e:
        print(f'Не удалось открыть {PORT}: {e}')
        return

    time.sleep(2)  # ждём автосброс Arduino (DTR)

    q = Queue(maxsize=10000)
    stop = Event()

    t_read  = Thread(target=reader_thread,  args=(ser, q, stop), daemon=True)
    t_write = Thread(target=writer_thread, args=(q, stop, csv_path, err_path), daemon=True)

    t_read.start()
    t_write.start()

    try:
        # Основной поток просто ждёт Ctrl+C
        while t_write.is_alive():
            t_write.join(timeout=0.5)
    except KeyboardInterrupt:
        print('\nОстановка...')

    stop.set()
    t_read.join(timeout=2)
    t_write.join(timeout=5)

    if ser.is_open:
        ser.close()

if __name__ == '__main__':
    main()