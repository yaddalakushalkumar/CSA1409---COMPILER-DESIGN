// Java Sample: While Loop & Logic
public class Main {
    public static void main(String[] args) {
        int count = 1;
        int total = 0;
        while (count <= 10) {
            total += count;
            count += 1;
        }
        System.out.println("Sum from 1 to 10:");
        System.out.println(total);
    }
}
