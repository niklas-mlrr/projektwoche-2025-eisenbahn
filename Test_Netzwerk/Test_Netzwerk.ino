import java.net.*;
import java.io.*;

ServerSocket server;
Socket socket;
BufferedReader reader;

void setup() {
  size(400, 200);
  background(0);
  fill(255);
  textAlign(CENTER);
  textSize(24);

  println("Waiting for Python to connect...");
  try {
    server = new ServerSocket(5005); // same port
    socket = server.accept();        // waits for the Python connection
    println("Connected!");
    reader = new BufferedReader(new InputStreamReader(socket.getInputStream()));
  } 
  catch (IOException e) {
    e.printStackTrace();
  }
}

void draw() {
  try {
    if (reader != null && reader.ready()) {
      String msg = reader.readLine();
      if (msg != null && msg.equals("clicked")) {
        println("Button clicked received!");
        background(random(255), random(255), random(255)); // action on signal
      }
    }
  } 
  catch (IOException e) {
    e.printStackTrace();
  }
}
