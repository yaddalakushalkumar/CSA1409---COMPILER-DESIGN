// C Sample: Factorial Loop
int n = 5;
int fact = 1;
int i = 1;

while (i <= n) {
    fact = fact * i;
    i = i + 1;
}

println("Factorial of 5:");
println(fact);
