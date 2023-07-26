import subprocess as sp
import os
import shutil

from ash.functions.functions_general import BC,ashexit, writestringtofile, pygrep, print_line_with_mainheader
import ash.settings_ash
"""
    Interface to the Multiwfn program
"""

#Use multiwfndir or just distribute multiwfn with ASH

#Multiwfn input:
 # ORCA: Molden file
 # Psi4: fchk file
 # MRCC: Molden and CCDENSITIES

#TODO: Support settings.ini file?

def multiwfn_run(moldenfile, fchkfile=None, option='density', mrccoutputfile=None, mrccdensityfile=None, multiwfndir=None, grid=3, numcores=1,
                 fragmentfiles=None, fockfile=None, openshell=False):
    print_line_with_mainheader("multiwfn_run")

    print("multiwfndir:", multiwfndir)
    print("Molden file:", moldenfile) #Inputfile is typically a Molden file
    print("Option:", option)
    print("Gridsetting:", grid)
    print("Numcores:", numcores)
    ############################
    #PREPARING MULTIWFN INPUT
    ############################
    if multiwfndir == None:
        print(BC.WARNING, "No multiwfndir argument passed to multiwfn_run. Attempting to find multiwfndir variable inside settings_ash", BC.END)
        try:
            print("settings_ash.settings_dict:", ash.settings_ash.settings_dict)
            multiwfndir=ash.settings_ash.settings_dict["multiwfndir"]
        except:
            print(BC.WARNING,"Found no multiwfndir variable in settings_ash module either.",BC.END)
            try:
                multiwfndir = os.path.dirname(shutil.which('Multiwfn'))
                print(BC.OKGREEN,"Found Multiwfn in path. Setting multiwfndir to:", multiwfndir, BC.END)
            except:
                print("Found no Multiwfn executable in path. Exiting... ")
                ashexit()
    
    #TODO: Update, once fchk files are supported 
    if os.path.isfile(moldenfile) is False:
        print(f"The selected Moldenfile: {moldenfile} does not exist. Exiting")
        ashexit()


    #MRCC density special case
    if option=="mrcc-density":
        print("Option mrcc-density chosen")
        if mrccoutputfile == None:
            print("MRCC outputfile should also be provided")
            ashexit()
        core_electrons = int(pygrep("Number of core electrons:",mrccoutputfile)[-1])
        print("Core electrons found in outputfile:", core_electrons)
        frozen_orbs = int(core_electrons/2)
        print("Frozen orbitals:", frozen_orbs)
        #Rename MRCC Molden file to mrcc.molden
        shutil.copy(moldenfile, "mrcc.molden")
        #First Multiwfn call. Create new Moldenfile based on correlated density
        write_multiwfn_input_option(option=option, grid=grid, frozenorbitals=frozen_orbs, densityfile=mrccdensityfile)
        print("Now calling Multiwfn to process the MRCC, Molden and CCDENSITIES files")
        with open("mwfnoptions") as input:
            sp.run([multiwfndir+'/Multiwfn', "mrcc.molden"], stdin=input)
        print("Multiwfn is done with this part")
        #Writes: mrccnew.molden a proper Molden WF file for MRCC WF. Now we can proceed
        option="density"
        moldenfile="mrccnew.molden"
        #Now make new mwfnoptions file for the density generation
        write_multiwfn_input_option(option="density", grid=grid)
    elif option == 'nocv':
        print("NOCV option")
        print("fragmentfiles:", fragmentfiles)
        print("Fockfile:", fockfile)
        if fragmentfiles == None:
            print("NOCV option requires fragmentfiles")
            ashexit()
        if fockfile == None:
            print("NOCV option requires fockfile option (can be ORCA output containing Fock-matrix printout)")
            ashexit()   
        #Create dummy-input
        write_multiwfn_input_option(option="nocv", grid=grid, fragmentfiles=fragmentfiles, openshell=openshell,
                                    fockfile=fockfile)
    #Density and other options (may or may not work)
    else:
        #Writing input
        write_multiwfn_input_option(option=option, grid=grid)
    
    ############################
    #RUNNING MULTIWFN
    ############################
    #TODO: Use logging instead
    input=open("mwfnoptions")
    output=open("multiwfn.out",'w')
    print(f"Now calling Multiwfn (using {numcores} cores)")
    sp.run([multiwfndir+'/Multiwfn', moldenfile,'-nt', str(numcores)], stdin=input, stdout=output)
    input.close()
    output.close()
    print("Multiwfn is done!")
    print()
    ############################
    #POST-PROCESSING OUTPUT
    ############################
    #NOTE: For now only Molden-file as main inputfile is supported.
    #TODO: Generalize below
    originputbasename=os.path.splitext(moldenfile)[0]

    if option =="density":
        print("Density option chosen")
        outputfile="density.cub"
        finaloutputfile=originputbasename+'_mwfn.cube'
        os.rename(outputfile, finaloutputfile)
        print("Electron density outputfile written:", finaloutputfile)
        return finaloutputfile
    elif option =="nocv":
        print("NOCV option was chosen.")
        print("Relevant Cube-files were created and NOCV output can be found in: NOCV.txt")
        print("See multiwfn.out for a log-file of the Multiwfn call.")
    elif option =="hirshfeld":
        print("Hirshfeld option was chosen.")

        #read file: 
        outputfile=moldenfile+'.chg'
        print(f"A file: {outputfile} was created")


#This function creates an inputfile of numbers that defines what Multiwfn does
def write_multiwfn_input_option(option=None, grid=3, frozenorbitals=None, densityfile=None,
                                fragmentfiles=None,fockfile=None, file4=None, openshell=False):
    #Create input formula as file
    if option == 'density':
        denstype=1
        #grid=3 #high-quality grid
        writeoutput=2 #Write Cubefile to current dir
        # 5 Output and plot specific property within a spatial region (calc. grid data)
        # 1 Electron density                 2 Gradient norm of electron density
        
        inputformula=f"""5 
{denstype}
{grid}
{writeoutput}
0
q
        """
    elif option == 'nocv':
        print("Writing Multiwfn inputfile for NOCV analysis")
        denstype=1
        numprodfrags=len(fragmentfiles)
        fragmentfilenames="\n".join(fragmentfiles)


        #If alpha/beta sets
        if openshell is True:
            openshell1="y"
            openshell2="y"
        else:
            openshell1=""
            openshell2=""
        #grid=3 #high-quality grid
        writeoutput=2 #Write Cubefile to current dir
        # 5 Output and plot specific property within a spatial region (calc. grid data)
        # 1 Electron density                 2 Gradient norm of electron density
        
        #-2 means generation of Fock matrix by information in file ? Is this valid. Output is not entirely correct
        #-1 means that we read Fock matrix externally. Can read ORCA output that contains Fock-matrix printout
        #%output Print[P_Iter_F] 1 end
        #Not perfect agreement with ORCA though, unclear why
        inputformula=f"""23
{numprodfrags}
{fragmentfilenames}
{openshell1}
{openshell2}
-1
{fockfile}
8
3
Pauli-deform.cube
9
orbdeform.cube
10
totdeform.cube
7
1
NOCVpair0.cube
2
NOCVpair1.cube
3
NOCVpair2.cube
4
NOCVpair3.cube
4
NOCVpair4.cube
q
-4

-10
q
        """
    elif option == 'hirshfeld':        
        inputformula=f"""7
1
1
y
0
q
        """

    elif option =="mrcc-density":
        if frozenorbitals == None:
            print("mrccdensity requires frozenorbitals")
            ashexit()
        if densityfile == None:
            print("mrccdensity requires densityfile")
            ashexit()
        #ASSUMES presence of file CCDENSITIES
        #Will write file: mrccnew.molden
        inputformula=f"""1000
97
./{densityfile}
{frozenorbitals}
y
100
2
6
mrccnew.molden
0
q

        """
    elif option =="mayerbondorder":
        pass
    elif option =="fuzzy_bondorder":
        pass
    else:
        print("write_multiwfn_input_option: unknown option")
        ashexit()
    #Write inputformula to disk
    writestringtofile(inputformula,"mwfnoptions")

    print("Wrote Multiwfn inputfile to disk: mwfnoptions")


#Analyze CCSD(T) wavefunctions from Psi4
#See chapter 4.A.8 in Multiwfn manual

def read_fchkfile(file):

    #Load multiwfn with file

    #Enter main function 200 and subfunction 16

    #transform density matrix into natural orbitals

    #Choose CCSD or other ?

    #For open-shell choose different NOs

    pass




#  0 Show molecular structure and view orbitals
#  1 Output all properties at a point
#  2 Topology analysis
#  3 Output and plot specific property in a line
#  4 Output and plot specific property in a plane
#  5 Output and plot specific property within a spatial region (calc. grid data)
#  6 Check & modify wavefunction
#  7 Population analysis and atomic charges
#  8 Orbital composition analysis
#  9 Bond order analysis
#  10 Plot total DOS, partial DOS, OPDOS, local DOS and photoelectron spectrum
#  11 Plot IR/Raman/UV-Vis/ECD/VCD/ROA/NMR spectrum
#  12 Quantitative analysis of molecular surface
#  13 Process grid data (No grid data is presented currently)
#  14 Adaptive natural density partitioning (AdNDP) analysis
#  15 Fuzzy atomic space analysis
#  16 Charge decomposition analysis (CDA) and plot orbital interaction diagram
#  17 Basin analysis                    18 Electron excitation analysis
#  19 Orbital localization analysis     20 Visual study of weak interaction
#  21 Energy decomposition analysis
#  100 Other functions (Part 1)         200 Other functions (Part 2)
#  300 Other functions (Part 3)
# 5
#  -10 Return to main menu
#  -2 Obtain of deformation property
#  -1 Obtain of promolecule property
#  0 Set custom operation
#              ----------- Avaliable real space functions -----------
#  1 Electron density                 2 Gradient norm of electron density
#  3 Laplacian of electron density    4 Value of orbital wavefunction
#  5 Electron spin density
#  6 Hamiltonian kinetic energy density K(r)
#  7 Lagrangian kinetic energy density G(r)
#  8 Electrostatic potential from nuclear charges
#  9 Electron Localization Function (ELF)
#  10 Localized orbital locator (LOL)
#  11 Local information entropy
#  12 Total electrostatic potential (ESP)
#  13 Reduced density gradient (RDG)     14 RDG with promolecular approximation
#  15 Sign(lambda2)*rho    16 Sign(lambda2)*rho with promolecular approximation
#  17 Correlation hole for alpha, ref. point:   0.00000   0.00000   0.00000
#  18 Average local ionization energy (ALIE)
#  19 Source function, mode: 1, ref. point:   0.00000   0.00000   0.00000
#  20 Electron delocalization range function EDR(r;d)
#  21 Orbital overlap distance function D(r)
#  22 Delta_g (promol. approx.)     23 Delta_g (Hirshfeld partition)
#  100 User-defined real space function, iuserfunc=    0


#  Please select a method to set up grid
#  -10 Set extension distance of grid range for mode 1~4, current:  6.000 Bohr
#  1 Low quality grid   , covering whole system, about 125000 points in total
#  2 Medium quality grid, covering whole system, about 512000 points in total
#  3 High quality grid  , covering whole system, about 1728000 points in total
#  4 Input the number of points or grid spacing in X,Y,Z, covering whole system
#  5 Input original point, translation vector and the number of points
#  6 Input center coordinate, number of points and extension distance
#  7 The same as 6, but input two atoms, the midpoint will be defined as center
#  8 Use grid setting of another cube file
#  10 Set box of grid data visually using a GUI window
#  100 Load a set of points from external file



#                  ============== Population analysis ==============
#  -2 Calculate interaction energy between fragments based on atomic charges
#  -1 Define fragment
#  0 Return
#  1 Hirshfeld atomic charge
#  2 Voronoi deformation density (VDD) atom population
#  5 Mulliken atom & basis function population analysis
#  6 Lowdin atom & basis function population analysis
#  7 Modified Mulliken atom population defined by Ros & Schuit (SCPA)
#  8 Modified Mulliken atom population defined by Stout & Politzer
#  9 Modified Mulliken atom population defined by Bickelhaupt
#  10 Becke atomic charge with atomic dipole moment correction
#  11 Atomic dipole corrected Hirshfeld atomic charge (ADCH) (recommended)
#  12 CHELPG ESP fitting atomic charge
#  13 Merz-Kollmann (MK) ESP fitting atomic charge
#  14 AIM atomic charge
#  15 Hirshfeld-I atomic charge
#  16 CM5 atomic charge
#  17 Electronegativity Equalization Method (EEM) atomic charge
#  18 Restrained ElectroStatic Potential (RESP) atomic charge
#  19 Gasteiger (PEOE) charge