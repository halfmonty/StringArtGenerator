package main

import (
	"fmt"
	"math"
	"image"
	"image/jpeg"
	"github.com/antha-lang/antha/antha/anthalib/num"
	"os"
	"io"
	"time"
	"strconv"
	"syscall/js"
)

//**********************//
//		Structs			//
//**********************//
type Coord struct {
	X float64
	Y float64
}

const PINS = 300
const MIN_DISTANCE = 30
const MAX_LINES = 4000
const LINE_WEIGHT = 8
var IMG_SIZE = 500
var IMG_SIZE_FL = float64(500)
var IMG_SIZE_SQ = 250000
var Pin_coords = []Coord{}
var SourceImage = []float64{}
var Line_cache_y = [][]float64{}
var Line_cache_x = [][]float64{}

//**********************//
//		Main			//
//**********************//

func init(){
	image.RegisterFormat("jpeg", "jpeg", jpeg.Decode, jpeg.DecodeConfig)
}

func main() {
	SourceImage = importPictureAndGetPixelArray()
	fmt.Println("Hello, world.")

	startTime := time.Now()
	calculatePinCoords()
	precalculateAllPotentialLines()
	calculateLines()
	endTime := time.Now()
	diff := endTime.Sub(startTime)
	fmt.Println(" precalculateAllPotentialLines Taken, " + strconv.FormatFloat(diff.Seconds(), 'f', 6, 64))

	fmt.Println("End")
}

func generateStringArt()

func importPictureAndGetPixelArray() []float64 {
	imgfile, _ := os.Open("./ae300.jpg")

	defer imgfile.Close()
	pixels, _ := getPixels(imgfile)
	return pixels
}

func getPixels(file io.Reader) ([]float64, error) {
	img, _, err := image.Decode(file)

    if err != nil {
        return nil, err
    }

    bounds := img.Bounds()
	width, height := bounds.Max.X, bounds.Max.Y
	IMG_SIZE = width
	IMG_SIZE_FL = float64(IMG_SIZE)
	IMG_SIZE_SQ =  IMG_SIZE * IMG_SIZE

    var pixels []float64
    for y := 0; y < height; y++ {
        for x := 0; x < width; x++ {
            pixels = append(pixels, rgbaToPixel(img.At(x, y).RGBA()))
        }
    }

    return pixels, nil
}

func rgbaToPixel(r uint32, g uint32, b uint32, a uint32) float64 {
    return float64(r / 257)
}

func calculatePinCoords() {
	pin_coords := [PINS]Coord{}

	center := float64(IMG_SIZE / 2)
	radius := float64(IMG_SIZE/2 - 1)

	for i:=0;i<PINS;i++ {
		angle := 2 * math.Pi * float64(i) / float64(PINS)
		pin_coords[i] = Coord{X : math.Floor(center + radius*math.Cos(angle)), Y : math.Floor(center + radius*math.Sin(angle))}
	}

	Pin_coords = pin_coords[:]
}

func precalculateAllPotentialLines() {
	line_cache_y := [PINS * PINS][]float64{}
	line_cache_x := [PINS * PINS][]float64{}

	for i := 0; i < PINS; i++ {
		for j := i + MIN_DISTANCE; j < PINS; j++ {
			x0 := Pin_coords[i].X
			y0 := Pin_coords[i].Y

			x1 := Pin_coords[j].X
			y1 := Pin_coords[j].Y

			d := math.Floor(math.Sqrt(float64((x1-x0)*(x1-x0) + (y1-y0)*(y1-y0))))
			xs := roundUpFloatArrayToInt(num.Linspace(float64(x0), float64(x1), int(d)))
			ys := roundUpFloatArrayToInt(num.Linspace(float64(y0), float64(y1), int(d)))

			line_cache_y[j*PINS+i] = ys
			line_cache_y[i*PINS+j] = ys
			line_cache_x[j*PINS+i] = xs
			line_cache_x[i*PINS+j] = xs
		}
	}
	Line_cache_y = line_cache_y[:][:]
	Line_cache_x = line_cache_x[:][:]
}

func roundUpFloatArrayToInt(arr []float64) []float64 {
	for i:= range arr {
		arr[i] = float64(int(arr[i]))
	}
	return arr
}

func calculateLines() {
	fmt.Println("Drawing Lines....")
	error := num.Sub(num.MulByConst(num.Ones(IMG_SIZE_SQ), float64(255)), SourceImage)

	line_sequence := make([]int, 1, 4096)
	current_pin := 0
	last_pins := make([]int, 20, 24)
	best_pin := -1
	line_err := float64(0)
	max_err := float64(0)
	index := 0
	inner_index := 0
	for i := 0; i < MAX_LINES; i++ {
		best_pin = -1
		line_err = float64(0)
		max_err = float64(0)

		for offset := MIN_DISTANCE; offset < PINS - MIN_DISTANCE; offset++ {
			test_pin := (current_pin + offset) % PINS
			if(contains(last_pins, test_pin)){
				continue;
			} else {
				inner_index = test_pin * PINS + current_pin

				line_err = getLineErr(error, Line_cache_y[inner_index], Line_cache_x[inner_index])
				if( line_err > max_err){
					max_err = line_err
					best_pin = test_pin
					index = inner_index
				}
			}
		}

		line_sequence = append(line_sequence, best_pin)

		coords1:=Line_cache_y[index]
		coords2:=Line_cache_x[index]
		for i := range coords1 {
			v := int((coords1[i] * IMG_SIZE_FL) + coords2[i])
			error[v] = error[v] - LINE_WEIGHT
		}

		last_pins = append(last_pins, best_pin)
		last_pins = last_pins[1:]
		current_pin = best_pin
	}	
	fmt.Println(line_sequence)
}

func getLineErr(err, coords1, coords2 []float64) float64 {
	sum := float64(0)
	for i:=0;i<len(coords1);i++{
		sum = sum + err[int((coords1[i] * IMG_SIZE_FL) + coords2[i])]
	}
	return sum
}

func contains(arr []int, num int) bool {
	for i := range arr {
		if arr[i] == num {
			return true
		}
	}
	return false
}