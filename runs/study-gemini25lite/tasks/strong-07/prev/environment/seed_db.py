import sqlite3
import subprocess
import random

def get_fee(duration, intensity):
    res = subprocess.run(['/usr/bin/calculate_fee', str(duration), str(intensity)], capture_output=True, text=True)
    try:
        return float(res.stdout.strip())
    except:
        return None

def main():
    conn = sqlite3.connect('usage.db')
    c = conn.cursor()
    c.execute('CREATE TABLE charges (id INTEGER PRIMARY KEY, duration REAL, intensity REAL, amount REAL)')
    
    random.seed(42)
    for i in range(500):
        duration = random.uniform(0.1, 200.0)
        intensity = random.uniform(0.1, 1.2)
        
        correct_amount = get_fee(duration, intensity)
        
        # Introduce errors in ~15% of records
        if random.random() < 0.15:
            amount = correct_amount + random.choice([0.01, -0.01, 0.0000001, 1.0])
        else:
            amount = correct_amount
            
        c.execute('INSERT INTO charges (duration, intensity, amount) VALUES (?, ?, ?)', (duration, intensity, amount))
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    main()
