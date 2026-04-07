*Construct dataset on EVs from 2016 to 2025
*Sylvain Weber
*27.03.2026

version 18
clear all
set more off
quietly {


*********************
*** Define locals ***
*********************
local year0 = 2016
local year1 = 2025 /*<- Adjust here if more recent waves are available*/
local T = `year1' - `year0'
local switchdrive "C:/Users/sylvain.weber/switchdrive/SHEDS/SHEDS (shared folders)/SHEDS Data - Core modules" /*<- Adjust path to location of SHEDS files in your system*/


***************************************
*** Load and combine SHEDS datasets ***
***************************************
tempfile sheds
save `sheds', emptyok
local listofvars id screen mob2_1 mob3_3 md_220 md_708
forv t = `year0'/`year1' {
	if `t'==2017 local listofvars `listofvars' mob3_change
	if `t'==2019 local listofvars `listofvars' mob3_3_other mob2_e
	if !inlist(`t',2022,2024,2026,2028) { /*No SHEDS waves in these years*/
		use `listofvars' using "`switchdrive'/SHEDS`t'", clear
		gen t = `t'
		append using `sheds'
		save `sheds', replace
	}
}

*Keep relevant observations
keep if screen!=3
drop screen

*Arrange dataset
order id t 
sort id t
xtset id t, yearly

*Decode missing values
mvdecode *, mv(-1=.a \ -2=.b \ -3=.c \ -4=.d)


**************************************************
*** Fill in missing values with historial data ***
**************************************************
*Fill in labels for mob3_3
la def engine_lab 4 "E85" 5 "Electric (including hybrid)", add // categories present in 2016-2018 but then removed for more detailed categories 6-8

/*
*Minor corrections (not applied here) are possible using text provided by respondents in mob3_3_other, e.g.:
recode mob3_3 (9=6) if mob3_3_other=="Hybrid Gas Bezin" | mob3_3_other=="Électricité et essence " | mob3_3_other=="hybrid essence et éléctrique"
recode mob3_3 (9=1) if mob3_3_other=="essence et bio gaz" | mob3_3_other=="nicht mein auto"
*/

*Fill in engine information using past observations if car was not changed
forv l = 1/`T' { 
	replace mob3_3 = l`l'.mob3_3 if mi(mob3_3) & !mob3_change
}


**************************************************
*** Presence of specific vehicles in household ***
**************************************************
gen car = mob2_1>0
la var car "Household owns a car (1) or not (0)"
gen ev = inlist(mob3_3,5,6,7,8) | mob2_e==1
la var ev "Household owns an EV (1) or not (0)"
gen hybrid = inlist(mob3_3,5,6,7) if t>=2019
la var hybrid "Household owns an hybrid (1) or not (0)"
gen elec = inlist(mob3_3,8) | mob2_e==1 if t>=2019
la var elec "Household owns a purely electric vehicle (1) or not (0)"


********************************************************
*** Numbers and shares of specific vehicles, by year ***
********************************************************
preserve
collapse (sum) mob2_1 car ev hybrid elec md_220 md_708 (min) minev=ev minhybrid=hybrid minelec=elec, by(t)
foreach type in ev hybrid elec {
	replace `type' = . if mi(min`type')
	drop min`type'
	gen `type'_share = `type'/mob2_1*100
	format `type'_share %03.2f
}
noisily: l /*Results are only displayed; not saved*/
restore


****************
*** FSO Data ***
****************
*For comparison, download and plot data from Federal Statistical Office (FSO) on hybrid and electric vehicles
*Source: https://www.bfs.admin.ch/bfs/en/home/statistics/mobility-transport/transport-infrastructure-vehicles/vehicles/road-vehicles-stock-level-motorisation.assetdetail.36410768.html
frame create fso /*Create a new frame*/
frame change fso /*Switch to frame fso*/

*Upload FSO data from API
local url "https://disseminate.stats.swiss/rest/data/CH1.MFZ_IVS,DF_MFZ_1_EMISSION,1.0.0/_T._T._T._T._T+PC+PH+DC+DH+HP+HD+EL+FC+GA+_O._T._T.A?startPeriod=2005&endPeriod=2025&dimensionAtObservation=AllDimensions&format=csvfilewithlabels"
import delimited "`url'", varnames(1) clear

*Clean and arrange dataset
keep if !mi(time_period)
keep fuel time_period obs_value 
gen f = fuel!=fuel[_n-1]
replace f = sum(f)
gen n = _n
levelsof f, local(fuels)
foreach l of local fuels {
	sum n if f==`l'
	local flab: di fuel[`r(min)']
	la def fuel_lab `l' "`flab'", modify
}
drop n
la val f fuel_lab
drop fuel
ren time_period t
ren obs_value obs
xtset f t

*Create variables with vehicle types
gen type = 1*(f==1) + 2*(inlist(f,3,5,6,7)) + 3*(inlist(f,8,9))
drop if type==0
collapse (sum) obs, by(type t)
reshape wide obs, i(t) j(type)
ren obs1 total
ren obs2 hybrid
ren obs3 elec

*Create vehicle shares
gen hybrid_share = hybrid/total*100
la var hybrid_share "Hybrid vehicles"
gen elec_share = elec/total*100
la var elec_share "Electric vehicles"
format *share %03.2f

*Plot shares
#d ;
tw scatter hybrid_share t, mlab(hybrid_share) mlabpos(12) 
|| scatter elec_share t, mlab(elec_share) mlabpos(3)
	legend(pos(6) row(1)) xti("") yti("%") ylab(,format(%2.0f)) 
	graphr(m(r=10))
;
#d cr


***************************************
*** Return to frame with SHEDS data ***
***************************************
frame change default

} // end quietly
exit