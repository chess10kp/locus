package core

import (
	"log"
	"time"

	"github.com/gotk3/gotk3/glib"
)

var (
	callbackCounter int64
)

// LoggedIdleAdd wraps glib.IdleAdd with timing and logging
func LoggedIdleAdd(source string, f func()) {
	callbackID := callbackCounter
	callbackCounter++

	startTime := time.Now()

	log.Printf("[IDLE] %s: scheduling callback #%d", source, callbackID)

	glib.IdleAdd(func() {
		callbackStart := time.Now()
		log.Printf("[IDLE] %s: callback #%d started (waited %v)", source, callbackID, callbackStart.Sub(startTime))

		defer func() {
			if r := recover(); r != nil {
				log.Printf("[IDLE] %s: callback #%d PANICKED: %v", source, callbackID, r)
			}
		}()

		f()

		duration := time.Since(callbackStart)
		totalWait := time.Since(startTime)
		log.Printf("[IDLE] %s: callback #%d completed in %v (total: %v)", source, callbackID, duration, totalWait)
	})
}

// LoggedIdleAddBool wraps glib.IdleAdd with a bool-returning function and logging
func LoggedIdleAddBool(source string, f func() bool) {
	callbackID := callbackCounter
	callbackCounter++

	startTime := time.Now()

	log.Printf("[IDLE-BOOL] %s: scheduling callback #%d", source, callbackID)

	glib.IdleAdd(func() bool {
		callbackStart := time.Now()
		log.Printf("[IDLE-BOOL] %s: callback #%d started (waited %v)", source, callbackID, callbackStart.Sub(startTime))

		defer func() {
			if r := recover(); r != nil {
				log.Printf("[IDLE-BOOL] %s: callback #%d PANICKED: %v", source, callbackID, r)
			}
		}()

		result := f()

		duration := time.Since(callbackStart)
		totalWait := time.Since(startTime)
		log.Printf("[IDLE-BOOL] %s: callback #%d completed (returned %v) in %v (total: %v)", source, callbackID, result, duration, totalWait)

		return result
	})
}

// LogOperation logs the start and duration of an operation
func LogOperation(source string, opName string, f func()) {
	startTime := time.Now()
	log.Printf("[OP] %s: starting %s", source, opName)

	defer func() {
		if r := recover(); r != nil {
			log.Printf("[OP] %s: %s PANICKED after %v: %v", source, opName, time.Since(startTime), r)
		} else {
			log.Printf("[OP] %s: %s completed in %v", source, opName, time.Since(startTime))
		}
	}()

	f()
}

// TimedOperation returns a function that logs execution time
func TimedOperation(source string, opName string, f func()) func() {
	return func() {
		LogOperation(source, opName, f)
	}
}
