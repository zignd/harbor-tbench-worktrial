"""Small numerical calibration primitives."""
def convert(value, source_factor, target_factor):
    return value*source_factor/target_factor

def affine(value, slope, intercept):
    return slope*value+intercept

def calibrated(value, source_factor, target_factor, slope, intercept):
    return affine(convert(value,source_factor,target_factor),slope,intercept)

def calibration_record(run, factors, value, unit):
    _,slope,intercept,target=run
    return calibrated(value,factors[unit],factors[target],slope,intercept)
