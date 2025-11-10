package usecases

import (
	"errors"
	"iot-server/entities"
	"iot-server/repositories"
)

type DeviceUseCase struct {
	DeviceRepo       repositories.DeviceRepository
	DeviceDataRepo   repositories.DeviceDataRepository
	DeviceModuleRepo repositories.DeviceModuleRepository
}

func NewDeviceUseCase(deviceRepo repositories.DeviceRepository, deviceDataRepo repositories.DeviceDataRepository, deviceModuleRepo repositories.DeviceModuleRepository) *DeviceUseCase {
	return &DeviceUseCase{
		DeviceRepo:       deviceRepo,
		DeviceDataRepo:   deviceDataRepo,
		DeviceModuleRepo: deviceModuleRepo,
	}
}

// CreateDevice creates a new device
func (uc *DeviceUseCase) CreateDevice(device *entities.Device) error {
	if device.Name == "" {
		return errors.New("device name is required")
	}
	if device.Type == "" {
		return errors.New("device type is required")
	}
	return uc.DeviceRepo.Create(device)
}

// GetDevice retrieves a device by ID
func (uc *DeviceUseCase) GetDevice(id string) (*entities.Device, error) {
	if id == "" {
		return nil, errors.New("device id is required")
	}
	return uc.DeviceRepo.GetByID(id)
}

// GetAllDevices retrieves all devices
func (uc *DeviceUseCase) GetAllDevices() ([]entities.Device, error) {
	return uc.DeviceRepo.GetAll()
}

// UpdateDevice updates a device
func (uc *DeviceUseCase) UpdateDevice(device *entities.Device) error {
	if device.ID == "" {
		return errors.New("device id is required")
	}

	// Check if device exists
	existing, err := uc.DeviceRepo.GetByID(device.ID)
	if err != nil {
		return errors.New("device not found")
	}

	// Update only provided fields
	if device.Name != "" {
		existing.Name = device.Name
	}
	if device.Type != "" {
		existing.Type = device.Type
	}
	if device.Status != "" {
		existing.Status = device.Status
	}

	return uc.DeviceRepo.Update(existing)
}

// DeleteDevice deletes a device
func (uc *DeviceUseCase) DeleteDevice(id string) error {
	if id == "" {
		return errors.New("device id is required")
	}

	// Check if device exists
	_, err := uc.DeviceRepo.GetByID(id)
	if err != nil {
		return errors.New("device not found")
	}

	return uc.DeviceRepo.Delete(id)
}

// ============= DeviceData Use Cases =============

// CreateDeviceData creates new device data
func (uc *DeviceUseCase) CreateDeviceData(data *entities.DeviceData) error {
	if data.DeviceID == "" {
		return errors.New("device_id is required")
	}

	// Verify device exists
	_, err := uc.DeviceRepo.GetByID(data.DeviceID)
	if err != nil {
		return errors.New("device not found")
	}

	return uc.DeviceDataRepo.Create(data)
}

// GetDeviceData retrieves device data by ID
func (uc *DeviceUseCase) GetDeviceData(id string) (*entities.DeviceData, error) {
	if id == "" {
		return nil, errors.New("data id is required")
	}
	return uc.DeviceDataRepo.GetByID(id)
}

// GetAllDeviceData retrieves all device data
func (uc *DeviceUseCase) GetAllDeviceData() ([]entities.DeviceData, error) {
	return uc.DeviceDataRepo.GetAll()
}

// GetDeviceDataByDeviceID retrieves all data for a specific device
func (uc *DeviceUseCase) GetDeviceDataByDeviceID(deviceID string) ([]entities.DeviceData, error) {
	if deviceID == "" {
		return nil, errors.New("device_id is required")
	}
	return uc.DeviceDataRepo.GetByDeviceID(deviceID)
}

// UpdateDeviceData updates device data
func (uc *DeviceUseCase) UpdateDeviceData(data *entities.DeviceData) error {
	if data.ID == "" {
		return errors.New("data id is required")
	}

	// Check if data exists
	existing, err := uc.DeviceDataRepo.GetByID(data.ID)
	if err != nil {
		return errors.New("device data not found")
	}

	// Update fields
	if data.Temperature != 0 {
		existing.Temperature = data.Temperature
	}
	if data.Humidity != 0 {
		existing.Humidity = data.Humidity
	}
	if data.Timestamp != "" {
		existing.Timestamp = data.Timestamp
	}

	return uc.DeviceDataRepo.Update(existing)
}

// DeleteDeviceData deletes device data
func (uc *DeviceUseCase) DeleteDeviceData(id string) error {
	if id == "" {
		return errors.New("data id is required")
	}

	// Check if data exists
	_, err := uc.DeviceDataRepo.GetByID(id)
	if err != nil {
		return errors.New("device data not found")
	}

	return uc.DeviceDataRepo.Delete(id)
}

// GetDevicesByUserID retrieves all devices for a specific user
func (uc *DeviceUseCase) GetDevicesByUserID(userID string) ([]entities.Device, error) {
	if userID == "" {
		return nil, errors.New("user_id is required")
	}
	return uc.DeviceRepo.GetByUserID(userID)
}

// ============= DeviceModule Use Cases =============

// CreateDeviceModule creates a new device module
func (uc *DeviceUseCase) CreateDeviceModule(module *entities.DeviceModule) error {
	if module.DeviceID == "" {
		return errors.New("device_id is required")
	}
	if module.UserID == "" {
		return errors.New("user_id is required")
	}

	// Verify device exists
	_, err := uc.DeviceRepo.GetByID(module.DeviceID)
	if err != nil {
		return errors.New("device not found")
	}

	return uc.DeviceModuleRepo.Create(module)
}

// GetDeviceModule retrieves a device module by ID
func (uc *DeviceUseCase) GetDeviceModule(id string) (*entities.DeviceModule, error) {
	if id == "" {
		return nil, errors.New("module id is required")
	}
	return uc.DeviceModuleRepo.GetByID(id)
}

// GetAllDeviceModules retrieves all device modules
func (uc *DeviceUseCase) GetAllDeviceModules() ([]entities.DeviceModule, error) {
	return uc.DeviceModuleRepo.GetAll()
}

// GetDeviceModulesByUserID retrieves all device modules for a specific user
func (uc *DeviceUseCase) GetDeviceModulesByUserID(userID string) ([]entities.DeviceModule, error) {
	if userID == "" {
		return nil, errors.New("user_id is required")
	}
	return uc.DeviceModuleRepo.GetByUserID(userID)
}

// GetDeviceModulesByDeviceID retrieves all modules for a specific device
func (uc *DeviceUseCase) GetDeviceModulesByDeviceID(deviceID string) ([]entities.DeviceModule, error) {
	if deviceID == "" {
		return nil, errors.New("device_id is required")
	}
	return uc.DeviceModuleRepo.GetByDeviceID(deviceID)
}

// UpdateDeviceModule updates a device module
func (uc *DeviceUseCase) UpdateDeviceModule(module *entities.DeviceModule) error {
	if module.ID == "" {
		return errors.New("module id is required")
	}

	// Check if module exists
	existing, err := uc.DeviceModuleRepo.GetByID(module.ID)
	if err != nil {
		return errors.New("device module not found")
	}

	// Update fields
	if module.Name != "" {
		existing.Name = module.Name
	}
	if module.DeviceID != "" {
		existing.DeviceID = module.DeviceID
	}
	if module.UserID != "" {
		existing.UserID = module.UserID
	}

	return uc.DeviceModuleRepo.Update(existing)
}

// DeleteDeviceModule deletes a device module
func (uc *DeviceUseCase) DeleteDeviceModule(id string) error {
	if id == "" {
		return errors.New("module id is required")
	}

	// Check if module exists
	_, err := uc.DeviceModuleRepo.GetByID(id)
	if err != nil {
		return errors.New("device module not found")
	}

	return uc.DeviceModuleRepo.Delete(id)
}
