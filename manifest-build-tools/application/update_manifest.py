#!/usr/bin/env python

# Copyright 2015, EMC, Inc.


import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import shutil

#pylint: disable=relative-import
import config
from RepositoryOperator import RepoOperator
from manifest import Manifest


class UpdateManifest(object):

    def __init__(self):
        """
        __repo - the repository url being updated in the manifest
        __branch - the branch name associated with __repo
        __sliced_branch - the branch name sliced at any forward slashes
        __commit - The commit id associated with the __repo and __branch that we want to update
        __manifest_repository_url - the repository url the points to the collection of manifest files
        __manifest_file - the desired manifest file to update which resides in __manifest_repository_url
        __cleanup_directories - the path/name of directories created are appended here for cleanup in task_cleanup
        __git_credentials - url, credentials pair for the access to github repos
        quiet - used for testing to minimize text written to a terminal
        repo_operator - Class instance of RepoOperator
        :return: None
        """
        self.__repo = None
        self.__branch = None
        self.__sliced_branch = None
        self.__commit = None
        self.__manifest_repository_url = None
        self.__manifest_file = None
        self.__cleanup_directories = []
        self.__git_credentials = None
        self.__updated_manifest = None
        self.__dryrun = False
        self.quiet = False
        self.repo_operator = RepoOperator()

    #pylint: disable=no-self-use
    def parse_args(self, args):
        """
        Take in values from the user.
        Repo, branch, and manifest_repo are required. This exits if they are not given.
        :return: Parsed args for assignment
        """
        parser = argparse.ArgumentParser()
        parser.add_argument('-n', '--dryrun',
                            help="Do not commit any changes, just print what would be done",
                            action="store_true")
        parser.add_argument("--repo",
                            help="Git url to match for updating the commit-id",
                            action="store")
        parser.add_argument("--branch",
                            help="The target branch for the named repo",
                            action="store")
        parser.add_argument("--manifest_repo",
                            help="The manifest repository URL.",
                            action="store")
        parser.add_argument("--commit",
                            help="OPTIONAL: The commit id to target an exact version",
                            action="store")
        parser.add_argument("--manifest_file",
                            help="The target manifest file to update. Searches through all if left empty.",
                            action="store")
        parser.add_argument("--git-credential",
                            help="Git URL and credentials comma separated",
                            action="append")
        parser.add_argument('--updated_manifest',
                            help="file containing the name of the updated manifest",
                            action="store")
        parser = parser.parse_args(args)

        return parser


    def assign_args(self, args):
        """
        Assign args to member variables and perform checks on branch and commit-id.
        :param args: Parsed args from the user
        :return:
        """
        if args.repo:
            self.__repo = args.repo
        else:
            print "\nMust specify repository url for cloning (--repo <git_url>)\n"

        if args.branch:
            self.__branch = args.branch
            if "/" in self.__branch:
                self.__sliced_branch = self.__branch.split("/")[-1]
            else:
                self.__sliced_branch = self.__branch
        else:
            print "\nMust specify a branch name (--branch <branch_name>)\n"

        if args.manifest_repo:
            self.__manifest_repository_url = args.manifest_repo
        else:
            print "\n Must specify a full repository url for retrieving <manifest>.json files\n"

        if args.dryrun:
            self.__dryrun = True
            self.repo_operator.setup_git_dryrun(self.__dryrun)

        if args.commit:
            self.__commit = args.commit

        if args.manifest_file:
            self.__manifest_file = args.manifest_file

        if args.git_credential:
            self.__git_credentials = args.git_credential
            self.repo_operator.setup_gitbit(credentials=self.__git_credentials)

        if args.updated_manifest:
            self.__updated_manifest = args.updated_manifest

    def check_args(self):
        """
        Check the values given for branch and commit-id
        """
        if self.__branch:
            try:
                self.repo_operator.check_branch(self.__repo, self.__sliced_branch)
            except RuntimeError as error:
                self.cleanup_and_exit(error, 1)
        if self.__commit:
            self.__check_commit()


    def __check_commit(self):
        """
        Check the format of the commit-id. It must be 40 hex characters.
        Exits if it is not.
        :return: None
        """
        commit_match = re.match('^[0-9a-fA-F]{40}$', self.__commit)
        if not commit_match:
            self.cleanup_and_exit("Id, '{0}' is not valid. It must be a 40 character hex string.".format(self.__commit), 1)


    def clone_manifest_repo(self):

        """
        Clone the repository which holds the manifest json files. Return that directory name. The directory
        is temporary and deleted in the cleanup_and_exit function
        :return: A string containing the name of the folder where the manifest repo was cloned
        """
        directory_name = tempfile.mkdtemp()

        if os.path.isdir(directory_name):
            self.__cleanup_directories.append(directory_name)
        else:
            self.cleanup_and_exit("Failed to make temporary directory for the repository: {0}".format(url), 1)
        try:
            manifest_repo = self.repo_operator.clone_repo(self.__manifest_repository_url, directory_name)
            return manifest_repo
        except RuntimeError as error:
            self.cleanup_and_exit(error, 1)

    def validate_manifest_files(self, *args):
        """
        validate several manifest files
        For example: validate_manifest_files(file1, file2) or
                     validate_manifest_files(file1, file2, file3)
        """
        validate_result = True
        for filename in args:
            try:
                manifest = Manifest(filename)
                manifest.validate_manifest()
                print "manifest file {0} is valid".format(filename)
            except KeyError as error:
                print "Failed to validate manifest file {0}".format(filename)
                print "\nERROR: \n{0}".format(error.message)
                validate_result = False
        return validate_result


    def cleanup_and_exit(self, message=None, code=0):
        """
        Delete all files and folders made during this job which are named in self.cleanup_directories
        :return: None
        """

        if not self.quiet:
            if message is not None:
                print "\nERROR: {0}".format(message)
            print "\nCleaning environment!\n"
        for item in self.__cleanup_directories:
            subprocess.check_output(["rm", "-rf", item])
        sys.exit(code)


    def get_updated_commit_message(self):
        """
        get the updated repository commit message
        """

        # get commit message based on the arguments repo, branch and commit
        directory_name = tempfile.mkdtemp()

        if os.path.isdir(directory_name):
            self.__cleanup_directories.append(directory_name)
        else:
            self.cleanup_and_exit("Failed to make temporary directory for the repository: {0}".format(url), 1)
        try:
            updated_repo_dir = self.repo_operator.clone_repo(self.__repo, directory_name)
            repo_commit_message = self.repo_operator.get_commit_message(updated_repo_dir, self.__commit)
            return repo_commit_message
        except RuntimeError as error:
            self.cleanup_and_exit(error, 1)


    def update_manifest_repo(self, dir_name, repo_commit_message):
        """
        Update manifest repository based on its contents and user arguments.
        :param dir_name: The directory of the repository
        :return: if repo is updated, return updated manifest file path and the manifest object
                 otherwise, return None, None
        """
        url_short_name = self.__repo.split('/')[-1][:-4]
        commit_message = "update to {0} */{1} commit #{2}\n{3}"\
                         .format(url_short_name, self.__branch, self.__commit, repo_commit_message)
        
        if self.__manifest_file is not None:
            path_name = os.path.join(dir_name, self.__manifest_file)
            if os.path.isfile(path_name):
                try:
                    manifest = Manifest(path_name, self.__git_credentials)
                    manifest.update_manifest(self.__repo, self.__branch, self.__commit)
                    if manifest.get_changed():
                        manifest.write_manifest_file(dir_name, commit_message, path_name, self.__dryrun)
                        return path_name, manifest
                    else:
                        print "No changes to {0}".format(manifest.get_name())
                except KeyError as error:
                    self.cleanup_and_exit("Failed to create an Manifest instance for the manifest file {0}\nError:{1}"\
                         .format(self.__manifest_file, error.message),1)

                except RuntimeError as error:
                    self.cleanup_and_exit("Failed to update manifest repo\nError:{0}".format(error.message),1)
        else:
            for item in os.listdir(dir_name):
                path_name = os.path.join(dir_name, item)
                if os.path.isfile(path_name):
                    try:
                        manifest = Manifest(path_name, self.__git_credentials)
                        manifest.update_manifest(self.__repo, self.__branch, self.__commit)
                        if manifest.get_changed():
                            manifest.write_manifest_file(dir_name, commit_message, path_name, self.__dryrun)
                            return path_name, manifest
                        else:
                            print "No changes to {0}".format(manifest.get_name())
                    except KeyError as error:
                        self.cleanup_and_exit("Failed to create an Manifest instance for the manifest file {0}\nError:{1}"\
                            .format(path_name, error.message),1)
                    except RuntimeError as error:
                        self.cleanup_and_exit("Failed to update manifest repo\nError:{0}".format(error.message),1)
        return None, None


    def write_downstream_parameters(self, filename, params):
        """
        Add/append downstream parameter (java variable value pair) to the given
        parameter file. If the file does not exist, then create the file.
        :param filename: The parameter file that will be used for making environment
         variable for downstream job.
        :param params: the parameters dictionary
        :return:
                None on success
                Raise any error if there is any
        """
        if filename is None:
            return

        with open(filename, 'w') as fp:
            try:
                for key in params:
                    entry = "{key}={value}\n".format(key=key, value=params[key])
                    fp.write(entry)
            except IOError as error:
                print "Unable to write parameter(s) for next step(s), exit"
                self.cleanup_and_exit(error, 1)

    def downstream_manifest_to_use(self, manifest_folder, file_with_path, manifest):
        """
        Write file which contains the name of the manifest file most recently updated.
        :param manifest_folder: the path of the manifest repository
        :param file_with_path: The path to be split to claim the filename
        :param manifest: the Manifest object of manifest file
        """
        file_name = file_with_path.split('/')[-1]
        downstream_parameters = {}
        downstream_parameters['MANIFEST_FILE_NAME'] = file_name
        downstream_parameters['BUILD_REQUIREMENTS'] = manifest.get_build_requirements()
        downstream_parameters['MANIFEST_FILE_REPO'] = self.__manifest_repository_url
        try:
            downstream_parameters['MANIFEST_FILE_BRANCH'] = self.repo_operator.get_current_branch(manifest_folder)
            downstream_parameters['MANIFEST_FILE_COMMIT'] = self.repo_operator.get_lastest_commit_id(manifest_folder)
        except RuntimeError as error:
            self.cleanup_and_exit(error, 1)       
        
        self.write_downstream_parameters(self.__updated_manifest, downstream_parameters)
        return

    def create_inject_properties_file(self):
        """
        Create inject.properties file for env vars injection after excute shell. 
        If upstream_manifest_name exists then copy it to inject.properties, else 
        create an empty inject.properties file to avoid exceptions throw by plugin.
        """
        if os.path.isfile(self.__updated_manifest):
            try:
                shutil.copyfile(self.__updated_manifest, "inject.properties")
            except IOError as error:
                print "ERROR: copy file {0} to inject.properties error.\n{1}".format(self.__updated_manifest, error)
                sys.exit(1)
        else:
            try:
                open('inject.properties','a').close()
            except IOError as error:
                print "ERROR: create empty file inject.properties error.\n{0}".format(error)
                sys.exit(1)
        return

def split_args(args):
    """
    split args that contains string list arg to multi args lists 
    :param args: the raw args, sys.argv[1:]
    :return args_list: the splited args
    """
    #check if all necessay args exist.
    update = UpdateManifest()
    passed_args = update.parse_args(args)
    update.check_args()
    
    #check if the items in repo, branch, commit are same number 
    if not (len(passed_args.repo.split())==len(passed_args.branch.split()) and \
            len(passed_args.repo.split())==len(passed_args.commit.split())):
        update.cleanup_and_exit("Id, repo or branch are not valid. Their numbers must be the same", 1)

    #split args to args list
    #args is like ['some_arg', 'value', 'repo', 'rackhd/on-http rackhd/on-core']
    #and then split it to two arg lists
    #['some_arg', 'value', 'repo', 'rackhd/on-http' ]
    #['some_arg', 'value', 'repo', 'rackhd/on-core' ]
    #only the value of args 'repo', 'branch', 'commit' will be splited and combine with other single
    #arg to generate arg lists
    args_list = []

    #number of loops equals number of repos(or commit, branch)
    #generate one new args list in one loop 
    for i in range(len(passed_args.repo.split())):
        tmp_args = []
        #save previous word in args list for recognize value of args 'repo', 'branch', 'commit'
        pre_word = ""

        #traverse args list generated one new arg list
        for word in args:
            if pre_word in ['--repo', '--branch', '--commit']:
                #choose the correct value
                tmp_args.append(word.split()[i])
            else:
                tmp_args.append(word)
            pre_word = word
        print "INFO tmp_args: {0}".format(tmp_args)
        args_list.append(tmp_args)
    return args_list

def main():
    args_list = split_args(sys.argv[1:])
    update = UpdateManifest()
    
    for args in args_list:
        passed_args = update.parse_args(args)
        update.assign_args(passed_args)
        update.check_args()

        manifest_folder = update.clone_manifest_repo()
        
        print "Starting validate manifest files in manifest repository"
        validate_result = True
        for filename in os.listdir(manifest_folder):
            pathname = os.path.join(manifest_folder, filename)
            if os.path.isfile(pathname):
                if not update.validate_manifest_files(pathname):
                    validate_result = False
        if not validate_result:
            update.cleanup_and_exit("Failed to validate manifest files in folder {0}".format(manifest_folder), 1)

        commit_message = update.get_updated_commit_message()
        update_filename, manifest = update.update_manifest_repo(manifest_folder, commit_message)
    
        if update_filename is not None:
            update.downstream_manifest_to_use(manifest_folder, update_filename, manifest)
            update.create_inject_properties_file()

    update.cleanup_and_exit()


if __name__ == "__main__":
    main()
    sys.exit(0)
