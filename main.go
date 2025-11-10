package main

import (
	"context"
	"iot-server/confs"
	"iot-server/db"
	"iot-server/server"
	"log"
	"os"

	"github.com/redis/go-redis/v9"
)

func main() {
	// load config
	err := confs.LoadConfig()
	if err != nil {
		log.Fatalf("Error loading config: %v", err)
	}

	// connect to database Postgres
	database, err := db.Connect()
	if err != nil {
		log.Fatalf("Failed to connect to DB: %v", err)
	}

	// make it connect to redis
	// Use REDIS_ADDR environment variable or default to localhost
	redisAddr := "localhost:6379"
	if addr := os.Getenv("REDIS_ADDR"); addr != "" {
		redisAddr = addr
	}

	redisClient := redis.NewClient(&redis.Options{
		Addr:     redisAddr,
		Password: "", // No password set
		DB:       0,  // Use default DB
	})
	_, err = redisClient.Ping(context.Background()).Result()
	if err != nil {
		log.Fatalf("Failed to connect to Redis: %v", err)
	}
	log.Printf("Connected to Redis at %s", redisAddr)

	// run server
	serverDb := server.NewServer(database)
	serverDb.Start()
}
