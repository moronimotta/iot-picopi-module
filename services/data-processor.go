package services

import (
	"iot-server/cache"
	"iot-server/db"
	"iot-server/entities"
	"log"
	"time"
)

type DataProcessor struct {
	cache    *cache.DeviceCache
	database db.Database
	interval time.Duration
}

func NewDataProcessor(database db.Database, tempThreshold, humidThreshold float64) *DataProcessor {
	return &DataProcessor{
		cache:    cache.NewDeviceCache(tempThreshold, humidThreshold),
		database: database,
		interval: 5 * time.Minute,
	}
}

func (dp *DataProcessor) Start() {
	ticker := time.NewTicker(dp.interval)
	go func() {
		for range ticker.C {
			dp.ProcessCachedData()
		}
	}()
}

func (dp *DataProcessor) ProcessCachedData() {
	// Get significant changes for all devices
	significantChanges := dp.cache.GetSignificantChanges()

	// Prepare bulk insert
	var allData []entities.DeviceData
	for _, deviceData := range significantChanges {
		allData = append(allData, deviceData...)
	}

	// Bulk insert if we have data
	if len(allData) > 0 {
		if err := dp.database.GetDB().Create(&allData).Error; err != nil {
			log.Printf("Error bulk inserting device data: %v", err)
		} else {
			log.Printf("Successfully inserted %d data points", len(allData))
		}
	}

	// Clear the cache after processing
	dp.cache.ClearCache()
}

// AddDataPoint adds a new data point to the cache
func (dp *DataProcessor) AddDataPoint(data entities.DeviceData) {
	dp.cache.AddDataPoint(data)
}

// GetAllCachedData returns all data currently in cache
func (dp *DataProcessor) GetAllCachedData() map[string][]cache.DeviceDataPoint {
	return dp.cache.GetAllCachedData()
}

// GetCacheStats returns statistics about the cache
func (dp *DataProcessor) GetCacheStats() map[string]interface{} {
	return dp.cache.GetCacheStats()
}
