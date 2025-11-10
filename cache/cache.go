package cache

import (
	"iot-server/entities"
	"sync"
	"time"
)

type DeviceDataPoint struct {
	Data      entities.DeviceData
	Timestamp time.Time
}

type DeviceCache struct {
	mu             sync.RWMutex
	deviceData     map[string][]DeviceDataPoint // map[deviceID][]dataPoints
	lastInserted   map[string]entities.DeviceData
	tempThreshold  float64 // Temperature change threshold (e.g., 0.5°C)
	humidThreshold float64 // Humidity change threshold (e.g., 2%)
}

func NewDeviceCache(tempThreshold, humidThreshold float64) *DeviceCache {
	return &DeviceCache{
		deviceData:     make(map[string][]DeviceDataPoint),
		lastInserted:   make(map[string]entities.DeviceData),
		tempThreshold:  tempThreshold,
		humidThreshold: humidThreshold,
	}
}

// AddDataPoint adds a new data point to the cache
func (dc *DeviceCache) AddDataPoint(data entities.DeviceData) {
	dc.mu.Lock()
	defer dc.mu.Unlock()

	deviceID := data.DeviceID
	point := DeviceDataPoint{
		Data:      data,
		Timestamp: time.Now(),
	}

	// Initialize slice if this is the first data point for this device
	if _, exists := dc.deviceData[deviceID]; !exists {
		dc.deviceData[deviceID] = make([]DeviceDataPoint, 0)
	}

	dc.deviceData[deviceID] = append(dc.deviceData[deviceID], point)
}

// GetSignificantChanges returns data points with significant changes for each device
func (dc *DeviceCache) GetSignificantChanges() map[string][]entities.DeviceData {
	dc.mu.RLock()
	defer dc.mu.RUnlock()

	significantChanges := make(map[string][]entities.DeviceData)

	for deviceID, dataPoints := range dc.deviceData {
		if len(dataPoints) == 0 {
			continue
		}

		// Always include the first reading
		significant := []entities.DeviceData{dataPoints[0].Data}
		lastSignificant := dataPoints[0].Data

		// Check intermediate points for significant changes
		for i := 1; i < len(dataPoints); i++ {
			current := dataPoints[i].Data

			// Check if change exceeds thresholds
			tempDiff := abs(current.Temperature - lastSignificant.Temperature)
			humidDiff := abs(current.Humidity - lastSignificant.Humidity)

			if tempDiff >= dc.tempThreshold || humidDiff >= dc.humidThreshold {
				significant = append(significant, current)
				lastSignificant = current
			}
		}

		// Always include the last reading if it's different from the last significant
		lastPoint := dataPoints[len(dataPoints)-1].Data
		if lastPoint != lastSignificant {
			significant = append(significant, lastPoint)
		}

		significantChanges[deviceID] = significant
	}

	return significantChanges
}

// GetAllCachedData returns all data points currently in cache
func (dc *DeviceCache) GetAllCachedData() map[string][]DeviceDataPoint {
	dc.mu.RLock()
	defer dc.mu.RUnlock()

	// Create a deep copy to avoid external modifications
	allData := make(map[string][]DeviceDataPoint)
	for deviceID, dataPoints := range dc.deviceData {
		allData[deviceID] = make([]DeviceDataPoint, len(dataPoints))
		copy(allData[deviceID], dataPoints)
	}

	return allData
}

// GetCacheStats returns statistics about the current cache
func (dc *DeviceCache) GetCacheStats() map[string]interface{} {
	dc.mu.RLock()
	defer dc.mu.RUnlock()

	totalPoints := 0
	deviceCount := len(dc.deviceData)

	for _, dataPoints := range dc.deviceData {
		totalPoints += len(dataPoints)
	}

	return map[string]interface{}{
		"total_devices":      deviceCount,
		"total_data_points":  totalPoints,
		"temp_threshold":     dc.tempThreshold,
		"humidity_threshold": dc.humidThreshold,
	}
}

// ClearCache clears the cached data after it's been processed
func (dc *DeviceCache) ClearCache() {
	dc.mu.Lock()
	defer dc.mu.Unlock()

	// Store last values before clearing
	for deviceID, dataPoints := range dc.deviceData {
		if len(dataPoints) > 0 {
			dc.lastInserted[deviceID] = dataPoints[len(dataPoints)-1].Data
		}
	}

	// Clear the cache
	dc.deviceData = make(map[string][]DeviceDataPoint)
}

func abs(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}
