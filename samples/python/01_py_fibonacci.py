# Python Sample: Fibonacci Series Generator
count = 7
t1 = 0
t2 = 1
i = 0

print("Python Fibonacci Series:")
while i < count:
    print(t1)
    next_val = t1 + t2
    t1 = t2
    t2 = next_val
    i = i + 1
