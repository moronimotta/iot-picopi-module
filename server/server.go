package server

import (
	"iot-server/db"
	"iot-server/handlers"
	httpHandler "iot-server/handlers/http"
	"iot-server/repositories"
	"iot-server/services"
	"iot-server/usecases"
	"iot-server/ws"
	"os"
	"strconv"

	"github.com/gin-gonic/gin"
)

type Server struct {
	app *gin.Engine
	db  db.Database
}

func NewServer(database db.Database) *Server {
	return &Server{
		app: gin.Default(),
		db:  database,
	}
}

func (s *Server) Start() {
	// Setup healthcheck route
	s.app.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{
			"status": "OK",
		})
	})

	// Initialize repositories
	deviceRepo := repositories.NewDevicePgRepository(s.db)
	deviceDataRepo := repositories.NewDeviceDataPgRepository(s.db)
	deviceModuleRepo := repositories.NewDeviceModulePgRepository(s.db)

	// Initialize use cases
	deviceUseCase := usecases.NewDeviceUseCase(deviceRepo, deviceDataRepo, deviceModuleRepo)
	commandsUseCase := usecases.NewCommandsUseCase(repositories.NewCommandPgRepository(s.db))

	// Initialize data processor (cache) with thresholds from env or defaults
	tempThresh := 0.5
	humidThresh := 2.0
	if v, ok := os.LookupEnv("TEMP_THRESHOLD"); ok {
		if f, err := strconv.ParseFloat(v, 64); err == nil {
			tempThresh = f
		}
	}
	if v, ok := os.LookupEnv("HUMID_THRESHOLD"); ok {
		if f, err := strconv.ParseFloat(v, 64); err == nil {
			humidThresh = f
		}
	}
	processor := services.NewDataProcessor(s.db, tempThresh, humidThresh)

	// Initialize handlers
	deviceHandler := httpHandler.NewDeviceHandler(deviceUseCase)
	deviceModuleHandler := httpHandler.NewDeviceModuleHandler(deviceUseCase)

	// WebSocket manager and handler
	manager := ws.NewManager()
	wsHandler := handlers.NewWSHandler(manager, deviceUseCase, processor)
	cmdHandler := httpHandler.NewCommandHandler(manager, commandsUseCase)
	cacheHandler := handlers.NewCacheHandler(processor)

	// Setup API routes
	api := s.app.Group("/api/v1")
	{
		// Device routes
		devices := api.Group("/devices")
		{
			devices.POST("", deviceHandler.CreateDevice)                                // Create device
			devices.GET("", deviceHandler.GetAllDevices)                                // Get all devices
			devices.GET("/:id/data", deviceHandler.GetDeviceDataByDeviceID)             // Get all data for a device (must come before /:id)
			devices.GET("/:id/modules", deviceModuleHandler.GetDeviceModulesByDeviceID) // Get all modules for a device
			devices.GET("/:id", deviceHandler.GetDevice)                                // Get device by ID
			devices.PUT("/:id", deviceHandler.UpdateDevice)                             // Update device
			devices.DELETE("/:id", deviceHandler.DeleteDevice)                          // Delete device
		}

		// Device data routes
		deviceData := api.Group("/device-data")
		{
			deviceData.POST("", deviceHandler.CreateDeviceData)       // Create device data
			deviceData.GET("", deviceHandler.GetAllDeviceData)        // Get all device data
			deviceData.GET("/:id", deviceHandler.GetDeviceData)       // Get device data by ID
			deviceData.PUT("/:id", deviceHandler.UpdateDeviceData)    // Update device data
			deviceData.DELETE("/:id", deviceHandler.DeleteDeviceData) // Delete device data
		}

		// Device module routes
		deviceModules := api.Group("/device-modules")
		{
			deviceModules.POST("", deviceModuleHandler.CreateDeviceModule)       // Create device module
			deviceModules.GET("", deviceModuleHandler.GetAllDeviceModules)       // Get all device modules
			deviceModules.GET("/:id", deviceModuleHandler.GetDeviceModule)       // Get device module by ID
			deviceModules.PUT("/:id", deviceModuleHandler.UpdateDeviceModule)    // Update device module
			deviceModules.DELETE("/:id", deviceModuleHandler.DeleteDeviceModule) // Delete device module
		}

		// User-specific routes
		users := api.Group("/users")
		{
			users.GET("/:user_id/devices", deviceModuleHandler.GetDevicesByUserID)              // Get all devices by user_id
			users.GET("/:user_id/device-modules", deviceModuleHandler.GetDeviceModulesByUserID) // Get all device modules by user_id
		}

		// Cache management endpoints
		cache := api.Group("/cache")
		{
			cache.POST("/process", cacheHandler.ProcessCache) // Trigger cache processing
			cache.GET("/data", cacheHandler.GetAllCachedData) // Get all cached data
			cache.GET("/stats", cacheHandler.GetCacheStats)   // Get cache statistics
		}

		// WebSocket-related HTTP endpoints
		api.POST("/commands", cmdHandler.Enqueue)                    // Enqueue and try WS send
		api.GET("/devices/connected", wsHandler.GetConnectedDevices) // List connected devices
		api.GET("/commands/poll", cmdHandler.Poll)                   // Devices fetch pending commands
		api.POST("/command-responses", cmdHandler.Ack)               // Devices acknowledge

		// Backward compatibility
		api.POST("/process-cache", cacheHandler.ProcessCache) // Trigger cache processing (deprecated, use /cache/process)
	}

	// WS endpoint for devices to connect
	s.app.GET("/ws", wsHandler.HandleDeviceWS)

	// Start server
	if err := s.app.Run("0.0.0.0:3536"); err != nil {
		panic(err)
	}
}
